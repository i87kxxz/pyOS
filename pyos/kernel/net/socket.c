#include "socket.h"
#include "net.h"
#include "string.h"
#include "usercopy.h"
#include "kernel.h"
#include "timer.h"
#include "debug.h"

struct sock {
    pyos_bool in_use;
    i32 type;       /* SOCK_STREAM / SOCK_DGRAM */
    i32 tcp_id;     /* net TCP pcb index, or -1 */
    u16 local_port;
    u32 remote_ip;
    u16 remote_port;
    pyos_bool connected;
    pyos_bool listening;
};

static struct sock socks[SOCK_MAX];

static i32 fd_to_idx(i32 fd) {
    if (fd < SOCK_FD_BASE || fd >= SOCK_FD_BASE + SOCK_MAX) return -1;
    return fd - SOCK_FD_BASE;
}

static i32 idx_to_fd(i32 idx) { return SOCK_FD_BASE + idx; }

pyos_bool sock_is_socket(i32 fd) {
    i32 i = fd_to_idx(fd);
    return (i >= 0 && socks[i].in_use) ? PYOS_TRUE : PYOS_FALSE;
}

i32 sock_socket(i32 domain, i32 type, i32 protocol) {
    (void)protocol;
    if (domain != AF_INET) return -1;
    if (type != SOCK_STREAM && type != SOCK_DGRAM) return -1;
    for (int i = 0; i < SOCK_MAX; i++) {
        if (!socks[i].in_use) {
            memset(&socks[i], 0, sizeof(socks[i]));
            socks[i].in_use = PYOS_TRUE;
            socks[i].type = type;
            socks[i].tcp_id = -1;
            return idx_to_fd(i);
        }
    }
    return -1;
}

i32 sock_bind(i32 fd, const struct sockaddr *addr, u32 addrlen) {
    i32 i = fd_to_idx(fd);
    if (i < 0 || !socks[i].in_use || !addr || addrlen < 8) return -1;
    const struct sockaddr_in *in = (const struct sockaddr_in *)addr;
    if (in->sin_family != AF_INET) return -1;
    socks[i].local_port = ntohs(in->sin_port);
    return 0;
}

i32 sock_connect(i32 fd, const struct sockaddr *addr, u32 addrlen) {
    i32 i = fd_to_idx(fd);
    if (i < 0 || !socks[i].in_use || !addr || addrlen < 8) return -1;
    if (socks[i].type != SOCK_STREAM) return -1;
    const struct sockaddr_in *in = (const struct sockaddr_in *)addr;
    u32 rip = ntohl(in->sin_addr);
    u16 rport = ntohs(in->sin_port);
    i32 tid = net_tcp_connect(rip, rport, 5000);
    if (tid < 0) return -1;
    socks[i].tcp_id = tid;
    socks[i].remote_ip = rip;
    socks[i].remote_port = rport;
    socks[i].connected = PYOS_TRUE;
    return 0;
}

i32 sock_listen(i32 fd, i32 backlog) {
    i32 i = fd_to_idx(fd);
    (void)backlog;
    if (i < 0 || !socks[i].in_use) return -1;
    socks[i].listening = PYOS_TRUE;
    return 0; /* server accept not fully implemented yet */
}

i32 sock_accept(i32 fd, struct sockaddr *addr, u32 *addrlen) {
    (void)fd;
    (void)addr;
    (void)addrlen;
    return -1; /* TCP listen/accept deferred; client path is supported */
}

i32 sock_send(i32 fd, const void *buf, u32 len, i32 flags) {
    (void)flags;
    i32 i = fd_to_idx(fd);
    if (i < 0 || !socks[i].in_use || !socks[i].connected) return -1;
    return net_tcp_send(socks[i].tcp_id, buf, len);
}

i32 sock_recv(i32 fd, void *buf, u32 len, i32 flags) {
    (void)flags;
    i32 i = fd_to_idx(fd);
    if (i < 0 || !socks[i].in_use || !socks[i].connected) return -1;
    return net_tcp_recv(socks[i].tcp_id, buf, len, 3000);
}

i32 sock_sendto(i32 fd, const void *buf, u32 len, i32 flags,
                const struct sockaddr *to, u32 tolen) {
    (void)to;
    (void)tolen;
    return sock_send(fd, buf, len, flags);
}

i32 sock_recvfrom(i32 fd, void *buf, u32 len, i32 flags,
                  struct sockaddr *from, u32 *fromlen) {
    (void)from;
    (void)fromlen;
    return sock_recv(fd, buf, len, flags);
}

i32 sock_setsockopt(i32 fd, i32 level, i32 optname, const void *optval, u32 optlen) {
    (void)level;
    (void)optname;
    (void)optval;
    (void)optlen;
    i32 i = fd_to_idx(fd);
    if (i < 0 || !socks[i].in_use) return -1;
    return 0; /* accept and ignore common options */
}

i32 sock_close(i32 fd) {
    i32 i = fd_to_idx(fd);
    if (i < 0 || !socks[i].in_use) return -1;
    if (socks[i].tcp_id >= 0) net_tcp_close(socks[i].tcp_id);
    memset(&socks[i], 0, sizeof(socks[i]));
    return 0;
}

static i32 copy_args(u32 args_ptr, u32 *out, u32 n) {
    if (!args_ptr) return -1;
    if (g_kernel_config.enable_user_mode) {
        if (copy_from_user(out, args_ptr, n * sizeof(u32)) != 0) return -1;
    } else {
        memcpy(out, (void *)(uintptr_t)args_ptr, n * sizeof(u32));
    }
    return 0;
}

i32 sock_socketcall(u32 call, u32 args_ptr) {
    u32 a[6];
    memset(a, 0, sizeof(a));

    switch (call) {
    case SOCKOP_SOCKET:
        if (copy_args(args_ptr, a, 3) != 0) return -1;
        return sock_socket((i32)a[0], (i32)a[1], (i32)a[2]);

    case SOCKOP_BIND: {
        if (copy_args(args_ptr, a, 3) != 0) return -1;
        struct sockaddr_in sa;
        memset(&sa, 0, sizeof(sa));
        u32 alen = a[2] < sizeof(sa) ? a[2] : sizeof(sa);
        if (g_kernel_config.enable_user_mode) {
            if (copy_from_user(&sa, a[1], alen) != 0) return -1;
        } else {
            memcpy(&sa, (void *)(uintptr_t)a[1], alen);
        }
        return sock_bind((i32)a[0], (struct sockaddr *)&sa, alen);
    }

    case SOCKOP_CONNECT: {
        if (copy_args(args_ptr, a, 3) != 0) return -1;
        struct sockaddr_in sa;
        memset(&sa, 0, sizeof(sa));
        u32 alen = a[2] < sizeof(sa) ? a[2] : sizeof(sa);
        if (g_kernel_config.enable_user_mode) {
            if (copy_from_user(&sa, a[1], alen) != 0) return -1;
        } else {
            memcpy(&sa, (void *)(uintptr_t)a[1], alen);
        }
        return sock_connect((i32)a[0], (struct sockaddr *)&sa, alen);
    }

    case SOCKOP_LISTEN:
        if (copy_args(args_ptr, a, 2) != 0) return -1;
        return sock_listen((i32)a[0], (i32)a[1]);

    case SOCKOP_ACCEPT:
        if (copy_args(args_ptr, a, 3) != 0) return -1;
        return sock_accept((i32)a[0], (struct sockaddr *)(uintptr_t)a[1],
                           (u32 *)(uintptr_t)a[2]);

    case SOCKOP_SEND: {
        if (copy_args(args_ptr, a, 4) != 0) return -1;
        char kbuf[512];
        u32 len = a[2] > sizeof(kbuf) ? sizeof(kbuf) : a[2];
        if (g_kernel_config.enable_user_mode) {
            if (copy_from_user(kbuf, a[1], len) != 0) return -1;
        } else {
            memcpy(kbuf, (void *)(uintptr_t)a[1], len);
        }
        return sock_send((i32)a[0], kbuf, len, (i32)a[3]);
    }

    case SOCKOP_RECV: {
        if (copy_args(args_ptr, a, 4) != 0) return -1;
        char kbuf[512];
        u32 maxlen = a[2] > sizeof(kbuf) ? sizeof(kbuf) : a[2];
        i32 n = sock_recv((i32)a[0], kbuf, maxlen, (i32)a[3]);
        if (n <= 0) return n;
        if (g_kernel_config.enable_user_mode) {
            if (copy_to_user(a[1], kbuf, (u32)n) != 0) return -1;
        } else {
            memcpy((void *)(uintptr_t)a[1], kbuf, (u32)n);
        }
        return n;
    }

    case SOCKOP_SENDTO: {
        if (copy_args(args_ptr, a, 6) != 0) return -1;
        char kbuf[512];
        u32 len = a[2] > sizeof(kbuf) ? sizeof(kbuf) : a[2];
        if (g_kernel_config.enable_user_mode) {
            if (copy_from_user(kbuf, a[1], len) != 0) return -1;
        } else {
            memcpy(kbuf, (void *)(uintptr_t)a[1], len);
        }
        return sock_sendto((i32)a[0], kbuf, len, (i32)a[3],
                           (const struct sockaddr *)(uintptr_t)a[4], a[5]);
    }

    case SOCKOP_RECVFROM: {
        if (copy_args(args_ptr, a, 6) != 0) return -1;
        char kbuf[512];
        u32 maxlen = a[2] > sizeof(kbuf) ? sizeof(kbuf) : a[2];
        i32 n = sock_recvfrom((i32)a[0], kbuf, maxlen, (i32)a[3],
                              (struct sockaddr *)(uintptr_t)a[4],
                              (u32 *)(uintptr_t)a[5]);
        if (n <= 0) return n;
        if (g_kernel_config.enable_user_mode) {
            if (copy_to_user(a[1], kbuf, (u32)n) != 0) return -1;
        } else {
            memcpy((void *)(uintptr_t)a[1], kbuf, (u32)n);
        }
        return n;
    }

    case SOCKOP_SETSOCKOPT: {
        if (copy_args(args_ptr, a, 5) != 0) return -1;
        return sock_setsockopt((i32)a[0], (i32)a[1], (i32)a[2],
                               (const void *)(uintptr_t)a[3], a[4]);
    }

    case SOCKOP_SHUTDOWN:
        if (copy_args(args_ptr, a, 2) != 0) return -1;
        return sock_close((i32)a[0]);

    default:
        debug_log("socketcall: unsupported");
        return -1;
    }
}

i32 sock_poll(i32 fd, i32 events, i32 timeout_ms) {
    (void)events;
    i32 i = fd_to_idx(fd);
    if (i < 0 || !socks[i].in_use) return 0;
    u32 start = timer_ms();
    for (;;) {
        net_poll();
        if (socks[i].connected && socks[i].tcp_id >= 0) {
            /* Non-blocking check: try zero-timeout peek via recv buffer */
            char tmp;
            i32 n = net_tcp_recv(socks[i].tcp_id, &tmp, 0, 0);
            (void)n;
            /* Always report writable when connected; readable if data pending is complex —
               report POLLIN|POLLOUT when established for busybox compatibility. */
            return 1;
        }
        if (timeout_ms >= 0 && (i32)(timer_ms() - start) >= timeout_ms) return 0;
        if (timeout_ms == 0) return 0;
    }
}

i32 sock_select(i32 nfds, void *readfds, void *writefds, void *exceptfds, void *timeout) {
    (void)exceptfds;
    /* Minimal: if any socket fd bit is set in read/write, poll briefly and succeed. */
    u32 start = timer_ms();
    u32 wait_ms = 100;
    if (timeout) {
        /* timeval {tv_sec, tv_usec} */
        i32 tv[2];
        if (g_kernel_config.enable_user_mode) {
            if (copy_from_user(tv, (u32)(uintptr_t)timeout, sizeof(tv)) != 0) return -1;
        } else {
            memcpy(tv, timeout, sizeof(tv));
        }
        wait_ms = (u32)tv[0] * 1000u + (u32)tv[1] / 1000u;
    }
    u8 rfds[32];
    u8 wfds[32];
    memset(rfds, 0, sizeof(rfds));
    memset(wfds, 0, sizeof(wfds));
    u32 bytes = ((u32)nfds + 7u) / 8u;
    if (bytes > sizeof(rfds)) bytes = sizeof(rfds);
    if (readfds) {
        if (g_kernel_config.enable_user_mode) {
            if (copy_from_user(rfds, (u32)(uintptr_t)readfds, bytes) != 0) return -1;
        } else {
            memcpy(rfds, readfds, bytes);
        }
    }
    if (writefds) {
        if (g_kernel_config.enable_user_mode) {
            if (copy_from_user(wfds, (u32)(uintptr_t)writefds, bytes) != 0) return -1;
        } else {
            memcpy(wfds, writefds, bytes);
        }
    }

    while (timer_ms() - start <= wait_ms) {
        net_poll();
        i32 ready_count = 0;
        for (i32 fd = 0; fd < nfds; fd++) {
            u32 byte = (u32)fd / 8u;
            u8 bit = (u8)(1u << (fd % 8));
            if (sock_is_socket(fd)) {
                if ((readfds && (rfds[byte] & bit)) || (writefds && (wfds[byte] & bit))) {
                    if (socks[fd_to_idx(fd)].connected) ready_count++;
                }
            }
        }
        if (ready_count > 0) {
            if (readfds) {
                if (g_kernel_config.enable_user_mode)
                    copy_to_user((u32)(uintptr_t)readfds, rfds, bytes);
                else
                    memcpy(readfds, rfds, bytes);
            }
            if (writefds) {
                if (g_kernel_config.enable_user_mode)
                    copy_to_user((u32)(uintptr_t)writefds, wfds, bytes);
                else
                    memcpy(writefds, wfds, bytes);
            }
            return ready_count;
        }
        if (wait_ms == 0) break;
    }
    return 0;
}
