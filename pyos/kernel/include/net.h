#ifndef PYOS_NET_H
#define PYOS_NET_H

#include "types.h"

/* QEMU user-net defaults */
#define NET_IP_ADDR   0x0A00020Fu  /* 10.0.2.15 */
#define NET_NETMASK   0xFFFFFF00u  /* 255.255.255.0 */
#define NET_GATEWAY   0x0A000202u  /* 10.0.2.2 */

#define ETH_ALEN 6
#define ETH_TYPE_IP  0x0800u
#define ETH_TYPE_ARP 0x0806u

#define IP_PROTO_ICMP 1
#define IP_PROTO_TCP  6
#define IP_PROTO_UDP  17

static inline u16 htons(u16 x) {
    return (u16)((x << 8) | (x >> 8));
}
static inline u16 ntohs(u16 x) { return htons(x); }
static inline u32 htonl(u32 x) {
    return ((x & 0x000000FFu) << 24) | ((x & 0x0000FF00u) << 8) |
           ((x & 0x00FF0000u) >> 8) | ((x & 0xFF000000u) >> 24);
}
static inline u32 ntohl(u32 x) { return htonl(x); }

i32 net_init(void);
pyos_bool net_is_ready(void);
void net_poll(void);

/* ICMP echo to dest (host order). Returns 0 on reply, -1 on failure. */
i32 net_ping(u32 dest_ip, u32 timeout_ms);

/* TCP client helpers used by socket layer */
i32 net_tcp_connect(u32 dst_ip, u16 dst_port, u32 timeout_ms);
i32 net_tcp_send(i32 sock_id, const void *data, u32 len);
i32 net_tcp_recv(i32 sock_id, void *buf, u32 maxlen, u32 timeout_ms);
void net_tcp_close(i32 sock_id);

u32 net_local_ip(void);
void net_get_mac(u8 mac[6]);

#endif
