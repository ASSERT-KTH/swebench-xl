# Task

## Segfault in new bulk query handling Diskbbq

### Elasticsearch Version

main

### Installed Plugins

_No response_

### Java Version

_bundled_

### OS Version

avx512 CPUs

### Problem Description

#
# A fatal error has been detected by the Java Runtime Environment:
#
#  SIGSEGV (0xb) at pc=0x00007f3d19094ac0, pid=182, tid=571
#
# JRE version: OpenJDK Runtime Environment (25.0.1+8) (build 25.0.1+8-27)
# Java VM: OpenJDK 64-Bit Server VM (25.0.1+8-27, mixed mode, tiered, compressed oops, compressed class ptrs, g1 gc, linux-amd64)
# Problematic frame:
# C  [libvec.so+0x2ac0]  dot7u_bulk_2+0x280
#
# Core dump will be written. Default location: /usr/share/elasticsearch/logs/core
#
# An error report file with more information is saved as:

### Steps to Reproduce

Bulk scoring on avx512

### Logs (if relevant)

_No response_

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `816d5015b6ab5c49bd0cdc00c7e1ed1c1a966780`
**Instance ID:** `elastic__elasticsearch-138317`
**Language:** `Java`
