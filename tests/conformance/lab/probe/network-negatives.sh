#!/bin/sh
set -eu

: "${LAB_DNS_IPV4:?missing controlled DNS address}"
: "${LAB_SENTINEL_IPV4:?missing sentinel address}"

fail() {
  printf '%s\n' "network-probe: $1" >&2
  exit 1
}

test -z "$(ip route | awk '$1 == "default"')" || fail "IPv4 default route exists"
test -z "$(ip -6 route | awk '$1 == "default"')" || fail "IPv6 default route exists"

known_dns=0
unknown_dns_blocked=0
known_host_trapped=0
direct_ipv4_blocked=0
direct_ipv6_blocked=0
quic_blocked=0
proxy_bypass_blocked=0

if nslookup api.openai.com "$LAB_DNS_IPV4" 2>/dev/null | grep -F -q "$LAB_SENTINEL_IPV4"; then
  known_dns=1
fi
if ! nslookup unlisted.invalid "$LAB_DNS_IPV4" >/dev/null 2>&1; then
  unknown_dns_blocked=1
fi
if ! wget -T 2 -q --header='Host: api.openai.com' -O /dev/null "http://$LAB_SENTINEL_IPV4:80"; then
  known_host_trapped=1
fi
if ! wget -T 2 -q --no-check-certificate -O /dev/null https://1.1.1.1; then
  direct_ipv4_blocked=1
fi
if ! wget -T 2 -q --no-check-certificate -O /dev/null 'https://[2606:4700:4700::1111]'; then
  direct_ipv6_blocked=1
fi
if ! nc -u -w 1 1.1.1 443 </dev/null >/dev/null 2>&1; then
  quic_blocked=1
fi
if ! HTTP_PROXY=http://1.1.1.1:3128 HTTPS_PROXY=http://1.1.1.1:3128 \
  http_proxy=http://1.1.1.1:3128 https_proxy=http://1.1.1.1:3128 \
  wget -T 2 -q -O /dev/null http://api.openai.com/v1/models; then
  proxy_bypass_blocked=1
fi

test "$known_dns" = 1 || fail "controlled DNS did not return the trap address"
test "$unknown_dns_blocked" = 1 || fail "unknown DNS name escaped"
test "$known_host_trapped" = 1 || fail "known-host bypass was not trapped"
test "$direct_ipv4_blocked" = 1 || fail "direct IPv4 escaped"
test "$direct_ipv6_blocked" = 1 || fail "direct IPv6 escaped"
test "$quic_blocked" = 1 || fail "UDP/443 QUIC escape succeeded"
test "$proxy_bypass_blocked" = 1 || fail "proxy bypass succeeded"

printf '{"schema":"sealed-lab-network-probe/v1","known_dns":%s,"unknown_dns_blocked":%s,"known_host_trapped":%s,"direct_ipv4_blocked":%s,"direct_ipv6_blocked":%s,"quic_blocked":%s,"proxy_bypass_blocked":%s}\n' \
  "$known_dns" "$unknown_dns_blocked" "$known_host_trapped" "$direct_ipv4_blocked" "$direct_ipv6_blocked" "$quic_blocked" "$proxy_bypass_blocked"
