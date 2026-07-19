#include "net.h"
#include "virtio_net.h"
#include "string.h"
#include "debug.h"
#include "timer.h"

#define ETH_HDR 14
#define ARP_PKT 28
#define IP_HDR  20
#define ICMP_HDR 8
#define TCP_HDR 20

#define ARP_OP_REQUEST 1
#define ARP_OP_REPLY   2
#define ICMP_ECHO      8
#define ICMP_ECHOREPLY 0

#define TCP_FIN 0x01
#define TCP_SYN 0x02
#define TCP_RST 0x04
#define TCP_PSH 0x08
#define TCP_ACK 0x10

#define TCP_CLOSED      0
#define TCP_SYN_SENT    1
#define TCP_ESTABLISHED 2
#define TCP_CLOSE_WAIT  3

#define MAX_TCP 4
#define RX_PKT_MAX 1600
#define TCP_RX_CAP 2048

struct eth_hdr {
    u8 dst[6];
    u8 src[6];
    u16 type;
} __attribute__((packed));

struct arp_pkt {
    u16 htype;
    u16 ptype;
    u8 hlen;
    u8 plen;
    u16 op;
    u8 sha[6];
    u32 spa;
    u8 tha[6];
    u32 tpa;
} __attribute__((packed));

struct ip_hdr {
    u8 ver_ihl;
    u8 tos;
    u16 tot_len;
    u16 id;
    u16 frag;
    u8 ttl;
    u8 proto;
    u16 check;
    u32 saddr;
    u32 daddr;
} __attribute__((packed));

struct icmp_hdr {
    u8 type;
    u8 code;
    u16 check;
    u16 id;
    u16 seq;
} __attribute__((packed));

struct tcp_hdr {
    u16 sport;
    u16 dport;
    u32 seq;
    u32 ack;
    u8 off;
    u8 flags;
    u16 win;
    u16 check;
    u16 urg;
} __attribute__((packed));

struct tcp_pcb {
    u8 state;
    u16 local_port;
    u16 remote_port;
    u32 remote_ip;
    u32 snd_seq;
    u32 snd_una;
    u32 rcv_nxt;
    u8 rx_buf[TCP_RX_CAP];
    u32 rx_len;
    pyos_bool in_use;
};

static u8 local_mac[6];
static u32 local_ip = NET_IP_ADDR;
static u32 gateway_ip = NET_GATEWAY;
static u32 netmask = NET_NETMASK;
static u8 gw_mac[6];
static pyos_bool gw_mac_valid;
static u32 arp_ip;
static u8 arp_mac[6];
static pyos_bool arp_valid;
static pyos_bool ready;
static u16 ip_id;
static u16 ephemeral_port = 40000;
static u16 icmp_id = 1;
static volatile pyos_bool icmp_reply_ok;
static u16 icmp_expect_seq;
static struct tcp_pcb tcps[MAX_TCP];

void net_poll(void); /* forward */

static u16 checksum(const void *data, u32 len) {
    const u16 *p = (const u16 *)data;
    u32 sum = 0;
    while (len > 1) {
        sum += *p++;
        len -= 2;
    }
    if (len) sum += *(const u8 *)p;
    while (sum >> 16) sum = (sum & 0xFFFF) + (sum >> 16);
    return (u16)~sum;
}

static u16 ip_checksum(struct ip_hdr *ip) {
    ip->check = 0;
    return checksum(ip, IP_HDR);
}

static void eth_send(const u8 dst[6], u16 type, const void *payload, u32 plen) {
    u8 frame[1514];
    struct eth_hdr *eh = (struct eth_hdr *)frame;
    for (int i = 0; i < 6; i++) {
        eh->dst[i] = dst[i];
        eh->src[i] = local_mac[i];
    }
    eh->type = htons(type);
    if (plen > sizeof(frame) - ETH_HDR) plen = sizeof(frame) - ETH_HDR;
    memcpy(frame + ETH_HDR, payload, plen);
    virtio_net_tx(frame, ETH_HDR + plen);
}

static void arp_send(u16 op, const u8 tha[6], u32 tpa) {
    struct arp_pkt a;
    memset(&a, 0, sizeof(a));
    a.htype = htons(1);
    a.ptype = htons(ETH_TYPE_IP);
    a.hlen = 6;
    a.plen = 4;
    a.op = htons(op);
    for (int i = 0; i < 6; i++) {
        a.sha[i] = local_mac[i];
        a.tha[i] = tha ? tha[i] : 0;
    }
    a.spa = htonl(local_ip);
    a.tpa = htonl(tpa);
    u8 bcast[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
    eth_send(op == ARP_OP_REQUEST ? bcast : tha, ETH_TYPE_ARP, &a, sizeof(a));
}

static i32 resolve_mac(u32 dest_ip, u8 out_mac[6], u32 timeout_ms) {
    u32 next = (dest_ip & netmask) == (local_ip & netmask) ? dest_ip : gateway_ip;
    if (next == gateway_ip && gw_mac_valid) {
        for (int i = 0; i < 6; i++) out_mac[i] = gw_mac[i];
        return 0;
    }
    if (arp_valid && arp_ip == next) {
        for (int i = 0; i < 6; i++) out_mac[i] = arp_mac[i];
        return 0;
    }

    u8 zero[6] = {0};
    arp_send(ARP_OP_REQUEST, zero, next);

    u32 start = timer_ms();
    while (timer_ms() - start < timeout_ms) {
        net_poll();
        if (next == gateway_ip && gw_mac_valid) {
            for (int i = 0; i < 6; i++) out_mac[i] = gw_mac[i];
            return 0;
        }
        if (arp_valid && arp_ip == next) {
            for (int i = 0; i < 6; i++) out_mac[i] = arp_mac[i];
            return 0;
        }
    }
    return -1;
}

static void ip_send(u32 dst_ip, u8 proto, const void *payload, u32 plen) {
    u8 pkt[IP_HDR + 1400];
    struct ip_hdr *ip = (struct ip_hdr *)pkt;
    memset(ip, 0, IP_HDR);
    ip->ver_ihl = 0x45;
    ip->tot_len = htons((u16)(IP_HDR + plen));
    ip->id = htons(ip_id++);
    ip->ttl = 64;
    ip->proto = proto;
    ip->saddr = htonl(local_ip);
    ip->daddr = htonl(dst_ip);
    ip->check = ip_checksum(ip);
    if (plen > sizeof(pkt) - IP_HDR) plen = sizeof(pkt) - IP_HDR;
    memcpy(pkt + IP_HDR, payload, plen);

    u8 dmac[6];
    if (resolve_mac(dst_ip, dmac, 1000) != 0) {
        debug_log("net: ARP failed");
        return;
    }
    eth_send(dmac, ETH_TYPE_IP, pkt, IP_HDR + plen);
}

static u16 tcp_checksum(u32 saddr, u32 daddr, const struct tcp_hdr *th, u32 tcp_len,
                        const void *payload, u32 plen) {
    u32 sum = 0;
    sum += (saddr >> 16) & 0xFFFF;
    sum += saddr & 0xFFFF;
    sum += (daddr >> 16) & 0xFFFF;
    sum += daddr & 0xFFFF;
    sum += htons(IP_PROTO_TCP);
    sum += htons((u16)tcp_len);

    const u16 *p = (const u16 *)th;
    u32 left = tcp_len - plen;
    while (left > 1) {
        sum += *p++;
        left -= 2;
    }
    if (left) sum += *(const u8 *)p;

    p = (const u16 *)payload;
    left = plen;
    while (left > 1) {
        sum += *p++;
        left -= 2;
    }
    if (left) sum += *(const u8 *)p;

    while (sum >> 16) sum = (sum & 0xFFFF) + (sum >> 16);
    return (u16)~sum;
}

static void tcp_send_seg(struct tcp_pcb *t, u8 flags, const void *data, u32 dlen) {
    u8 buf[TCP_HDR + 1400];
    struct tcp_hdr *th = (struct tcp_hdr *)buf;
    memset(th, 0, TCP_HDR);
    th->sport = htons(t->local_port);
    th->dport = htons(t->remote_port);
    th->seq = htonl(t->snd_seq);
    th->ack = htonl(t->rcv_nxt);
    th->off = (5 << 4);
    th->flags = flags;
    th->win = htons(8192);
    if (dlen && data) {
        if (dlen > sizeof(buf) - TCP_HDR) dlen = sizeof(buf) - TCP_HDR;
        memcpy(buf + TCP_HDR, data, dlen);
    } else {
        dlen = 0;
    }
    th->check = 0;
    th->check = tcp_checksum(htonl(local_ip), htonl(t->remote_ip), th, TCP_HDR + dlen,
                             buf + TCP_HDR, dlen);
    ip_send(t->remote_ip, IP_PROTO_TCP, buf, TCP_HDR + dlen);
    if (flags & TCP_SYN) t->snd_seq++;
    else if (dlen) t->snd_seq += dlen;
    if (flags & TCP_FIN) t->snd_seq++;
}

static struct tcp_pcb *tcp_find(u32 rip, u16 rport, u16 lport) {
    for (int i = 0; i < MAX_TCP; i++) {
        if (!tcps[i].in_use) continue;
        if (tcps[i].remote_ip == rip && tcps[i].remote_port == rport &&
            tcps[i].local_port == lport)
            return &tcps[i];
    }
    return 0;
}

static void handle_tcp(u32 sip, const u8 *tcp_data, u32 len) {
    if (len < TCP_HDR) return;
    const struct tcp_hdr *th = (const struct tcp_hdr *)tcp_data;
    u16 sport = ntohs(th->sport);
    u16 dport = ntohs(th->dport);
    u8 flags = th->flags;
    u32 seq = ntohl(th->seq);
    u32 data_off = (th->off >> 4) * 4;
    if (data_off < TCP_HDR || data_off > len) return;
    u32 plen = len - data_off;
    const u8 *payload = tcp_data + data_off;

    struct tcp_pcb *t = tcp_find(sip, sport, dport);
    if (!t) return;

    if (flags & TCP_RST) {
        t->state = TCP_CLOSED;
        return;
    }

    if (t->state == TCP_SYN_SENT && (flags & TCP_SYN) && (flags & TCP_ACK)) {
        t->rcv_nxt = seq + 1;
        t->snd_una = ntohl(th->ack);
        t->state = TCP_ESTABLISHED;
        tcp_send_seg(t, TCP_ACK, 0, 0);
        return;
    }

    if (t->state == TCP_ESTABLISHED) {
        if (plen > 0) {
            u32 room = TCP_RX_CAP - t->rx_len;
            u32 copy = plen < room ? plen : room;
            if (copy) {
                memcpy(t->rx_buf + t->rx_len, payload, copy);
                t->rx_len += copy;
            }
            t->rcv_nxt = seq + plen;
            tcp_send_seg(t, TCP_ACK, 0, 0);
        }
        if (flags & TCP_FIN) {
            t->rcv_nxt = seq + 1;
            tcp_send_seg(t, TCP_ACK | TCP_FIN, 0, 0);
            t->state = TCP_CLOSED;
        }
    }
}

static void handle_icmp(u32 sip, const u8 *icmp_data, u32 len) {
    if (len < ICMP_HDR) return;
    const struct icmp_hdr *ic = (const struct icmp_hdr *)icmp_data;
    if (ic->type == ICMP_ECHO) {
        u8 reply[1500];
        if (len > sizeof(reply)) len = sizeof(reply);
        memcpy(reply, icmp_data, len);
        struct icmp_hdr *ric = (struct icmp_hdr *)reply;
        ric->type = ICMP_ECHOREPLY;
        ric->check = 0;
        ric->check = checksum(reply, len);
        ip_send(sip, IP_PROTO_ICMP, reply, len);
    } else if (ic->type == ICMP_ECHOREPLY) {
        if (ntohs(ic->id) == icmp_id && ntohs(ic->seq) == icmp_expect_seq) {
            icmp_reply_ok = PYOS_TRUE;
        }
    }
}

static void handle_ip(const u8 *ip_data, u32 len) {
    if (len < IP_HDR) return;
    const struct ip_hdr *ip = (const struct ip_hdr *)ip_data;
    if ((ip->ver_ihl >> 4) != 4) return;
    u32 ihl = (ip->ver_ihl & 0xF) * 4;
    if (ihl < IP_HDR || ihl > len) return;
    u32 tot = ntohs(ip->tot_len);
    if (tot > len) tot = len;
    if (tot < ihl) return;
    u32 sip = ntohl(ip->saddr);
    u32 dip = ntohl(ip->daddr);
    if (dip != local_ip && dip != 0xFFFFFFFFu) return;
    const u8 *payload = ip_data + ihl;
    u32 plen = tot - ihl;
    if (ip->proto == IP_PROTO_ICMP) handle_icmp(sip, payload, plen);
    else if (ip->proto == IP_PROTO_TCP) handle_tcp(sip, payload, plen);
}

static void handle_frame(const u8 *frame, u32 len) {
    if (len < ETH_HDR) return;
    const struct eth_hdr *eh = (const struct eth_hdr *)frame;
    u16 type = ntohs(eh->type);
    if (type == ETH_TYPE_ARP) {
        if (len < ETH_HDR + sizeof(struct arp_pkt)) return;
        const struct arp_pkt *a = (const struct arp_pkt *)(frame + ETH_HDR);
        if (ntohs(a->op) == ARP_OP_REQUEST && ntohl(a->tpa) == local_ip) {
            arp_send(ARP_OP_REPLY, a->sha, ntohl(a->spa));
        } else if (ntohs(a->op) == ARP_OP_REPLY) {
            u32 spa = ntohl(a->spa);
            for (int i = 0; i < 6; i++) arp_mac[i] = a->sha[i];
            arp_ip = spa;
            arp_valid = PYOS_TRUE;
            if (spa == gateway_ip) {
                for (int i = 0; i < 6; i++) gw_mac[i] = a->sha[i];
                gw_mac_valid = PYOS_TRUE;
            }
        }
    } else if (type == ETH_TYPE_IP) {
        handle_ip(frame + ETH_HDR, len - ETH_HDR);
    }
}

void net_poll(void) {
    if (!ready) return;
    u8 pkt[RX_PKT_MAX];
    for (int i = 0; i < 16; i++) {
        i32 n = virtio_net_rx(pkt, sizeof(pkt));
        if (n <= 0) break;
        handle_frame(pkt, (u32)n);
    }
}

i32 net_init(void) {
    ready = PYOS_FALSE;
    gw_mac_valid = PYOS_FALSE;
    memset(tcps, 0, sizeof(tcps));

    if (virtio_net_init() != 0) return -1;
    virtio_net_get_mac(local_mac);
    local_ip = NET_IP_ADDR;
    gateway_ip = NET_GATEWAY;
    netmask = NET_NETMASK;
    ready = PYOS_TRUE;
    debug_log("net: stack ready (10.0.2.15)");

    /* Resolve gateway then ping */
    u8 mac[6];
    if (resolve_mac(gateway_ip, mac, 2000) != 0) {
        debug_log("net: gateway ARP failed");
    } else {
        debug_log("net: gateway ARP ok");
    }

    if (net_ping(gateway_ip, 3000) == 0) {
        debug_log("net: ping 10.0.2.2 ok");
    } else {
        debug_log("net: ping 10.0.2.2 fail");
    }
    return 0;
}

pyos_bool net_is_ready(void) { return ready; }
u32 net_local_ip(void) { return local_ip; }
void net_get_mac(u8 mac_out[6]) {
    for (int i = 0; i < 6; i++) mac_out[i] = local_mac[i];
}

i32 net_ping(u32 dest_ip, u32 timeout_ms) {
    if (!ready) return -1;
    u8 pkt[ICMP_HDR + 16];
    struct icmp_hdr *ic = (struct icmp_hdr *)pkt;
    memset(pkt, 0, sizeof(pkt));
    ic->type = ICMP_ECHO;
    ic->code = 0;
    ic->id = htons(icmp_id);
    icmp_expect_seq++;
    ic->seq = htons(icmp_expect_seq);
    for (int i = 0; i < 16; i++) pkt[ICMP_HDR + i] = (u8)('a' + i);
    ic->check = 0;
    ic->check = checksum(pkt, sizeof(pkt));
    icmp_reply_ok = PYOS_FALSE;
    ip_send(dest_ip, IP_PROTO_ICMP, pkt, sizeof(pkt));

    u32 start = timer_ms();
    while (timer_ms() - start < timeout_ms) {
        net_poll();
        if (icmp_reply_ok) return 0;
    }
    return -1;
}

i32 net_tcp_connect(u32 dst_ip, u16 dst_port, u32 timeout_ms) {
    if (!ready) return -1;
    int slot = -1;
    for (int i = 0; i < MAX_TCP; i++) {
        if (!tcps[i].in_use) {
            slot = i;
            break;
        }
    }
    if (slot < 0) return -1;

    struct tcp_pcb *t = &tcps[slot];
    memset(t, 0, sizeof(*t));
    t->in_use = PYOS_TRUE;
    t->state = TCP_SYN_SENT;
    t->local_port = ephemeral_port++;
    if (ephemeral_port < 40000) ephemeral_port = 40000;
    t->remote_port = dst_port;
    t->remote_ip = dst_ip;
    t->snd_seq = 1000 + (u32)slot * 1000u;

    tcp_send_seg(t, TCP_SYN, 0, 0);

    u32 start = timer_ms();
    while (timer_ms() - start < timeout_ms) {
        net_poll();
        if (t->state == TCP_ESTABLISHED) return slot;
        if (t->state == TCP_CLOSED) break;
    }
    t->in_use = PYOS_FALSE;
    return -1;
}

i32 net_tcp_send(i32 sock_id, const void *data, u32 len) {
    if (sock_id < 0 || sock_id >= MAX_TCP) return -1;
    struct tcp_pcb *t = &tcps[sock_id];
    if (!t->in_use || t->state != TCP_ESTABLISHED) return -1;
    u32 sent = 0;
    while (sent < len) {
        u32 chunk = len - sent;
        if (chunk > 1024) chunk = 1024;
        tcp_send_seg(t, TCP_PSH | TCP_ACK, (const u8 *)data + sent, chunk);
        sent += chunk;
        net_poll();
    }
    return (i32)len;
}

i32 net_tcp_recv(i32 sock_id, void *buf, u32 maxlen, u32 timeout_ms) {
    if (sock_id < 0 || sock_id >= MAX_TCP) return -1;
    struct tcp_pcb *t = &tcps[sock_id];
    if (!t->in_use) return -1;

    u32 start = timer_ms();
    while (t->rx_len == 0 && t->state == TCP_ESTABLISHED) {
        net_poll();
        if (timeout_ms == 0) return 0;
        if (timer_ms() - start >= timeout_ms) return 0;
    }
    if (t->rx_len == 0) return 0;
    u32 n = t->rx_len < maxlen ? t->rx_len : maxlen;
    memcpy(buf, t->rx_buf, n);
    if (n < t->rx_len) {
        memmove(t->rx_buf, t->rx_buf + n, t->rx_len - n);
        t->rx_len -= n;
    } else {
        t->rx_len = 0;
    }
    return (i32)n;
}

void net_tcp_close(i32 sock_id) {
    if (sock_id < 0 || sock_id >= MAX_TCP) return;
    struct tcp_pcb *t = &tcps[sock_id];
    if (!t->in_use) return;
    if (t->state == TCP_ESTABLISHED) {
        tcp_send_seg(t, TCP_FIN | TCP_ACK, 0, 0);
        net_poll();
    }
    t->in_use = PYOS_FALSE;
    t->state = TCP_CLOSED;
}
