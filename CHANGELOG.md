# Changelog

## 1.2 (January 15, 2024)

- [Drop support for Python 2.7](https://github.com/Changaco/psycopg2-pool/commit/0b6ff0e5cf18c72ef48d7f57d12a9bd388dcc162)
- [Call `psycopg2.connect` instead of `psycopg2._connect`](https://github.com/Changaco/psycopg2-pool/pull/3), for compatibility with tools like AWS XRay.

## 1.1 (October 8, 2019)

- [Fixes the discarding of extraneous connections](https://github.com/Changaco/psycopg2-pool/pull/1)
- [Fixes `ThreadSafeConnectionPool.__slots__`](https://github.com/Changaco/psycopg2-pool/commit/0145f44efc21a2e1ec078c6d29a4649f9978380f)

## 1.0 (October 6, 2019)

Initial release.
