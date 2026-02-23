# Task

## Improve concurrency design of `EnterpriseGeoIpDownloader`

Refactors `EnterpriseGeoIpDownloader` to avoid race conditions between the periodic and on-demand runs. See the discussion on #126124 for more details on the previously existing race condition.

With this new approach, we make a distinction between the periodic and on-demand runs. The periodic runs simply run periodically on the configured poll interval. The on-demand runs are typically triggered by changes in the cluster state to the GeoIP metadata, and require running the downloader immediately to download any GeoIP databases that were just added by a user. By using an `AtomicInteger` to track the number of on-demand runs that were requested concurrently, we can guarantee that a new cluster state will result in the downloader running and avoid the downloader from running concurrently.

While the (non-enterprise) `GeoIpDownloader` has the exact same concurrency implementation, we scope this PR to just the enterprise downloader to focus discussions on the design changes. A follow-up PR will modify the `GeoIpDownloader` to have the same implementation as the enterprise downloader.

Fixes #126124

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `ffbf05c994b0364f081b75ff0a146957ec005555`
**Instance ID:** `elastic__elasticsearch-134223`
**Language:** `Java`
