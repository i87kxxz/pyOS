#ifndef PYOS_SOCKET_H
#define PYOS_SOCKET_H

#include "types.h"

/* Linux i386 socketcall sub-calls */
#define SOCKOP_SOCKET      1
#define SOCKOP_BIND        2
#define SOCKOP_CONNECT     3
#define SOCKOP_LISTEN      4
#define SOCKOP_ACCEPT      5
#define SOCKOP_GETSOCKNAME 6
#define SOCKOP_GETPEERNAME 7
#define SOCKOP_SOCKETPAIR  8
#define SOCKOP_SEND        9
#define SOCKOP_RECV        10
#define SOCKOP_SENDTO      11
#define SOCKOP_RECVFROM    12
#define SOCKOP_SHUTDOWN    13
#define SOCKOP_SETSOCKOPT  14
#define SOCKOP_GETSOCKOPT  15

#define AF_INET     2
#define SOCK_STREAM 1
#define SOCK_DGRAM  2
#define IPPROTO_IP  0
#define IPPROTO_TCP 6
#define IPPROTO_UDP 17

#define SOL_SOCKET 1
#define SO_REUSEADDR 2
#define SO_KEEPALIVE 9

#define SOCK_FD_BASE 64
#define SOCK_MAX     8

struct sockaddr_in {
    u16 sin_family;
    u16 sin_port;     /* network order */
    u32 sin_addr;     /* network order */
    u8  sin_zero[8];
} __attribute__((packed));

struct sockaddr {
    u16 sa_family;
    char sa_data[14];
} __attribute__((packed));

i32 sock_socket(i32 domain, i32 type, i32 protocol);
i32 sock_bind(i32 fd, const struct sockaddr *addr, u32 addrlen);
i32 sock_connect(i32 fd, const struct sockaddr *addr, u32 addrlen);
i32 sock_listen(i32 fd, i32 backlog);
i32 sock_accept(i32 fd, struct sockaddr *addr, u32 *addrlen);
i32 sock_send(i32 fd, const void *buf, u32 len, i32 flags);
i32 sock_recv(i32 fd, void *buf, u32 len, i32 flags);
i32 sock_sendto(i32 fd, const void *buf, u32 len, i32 flags,
                const struct sockaddr *to, u32 tolen);
i32 sock_recvfrom(i32 fd, void *buf, u32 len, i32 flags,
                  struct sockaddr *from, u32 *fromlen);
i32 sock_setsockopt(i32 fd, i32 level, i32 optname, const void *optval, u32 optlen);
i32 sock_close(i32 fd);
pyos_bool sock_is_socket(i32 fd);

/* Linux socketcall multiplexer: call = SOCKOP_*, args = user ptr to u32[]. */
i32 sock_socketcall(u32 call, u32 args_ptr);

/* poll/select helpers */
i32 sock_poll(i32 fd, i32 events, i32 timeout_ms);
i32 sock_select(i32 nfds, void *readfds, void *writefds, void *exceptfds, void *timeout);

#endif
