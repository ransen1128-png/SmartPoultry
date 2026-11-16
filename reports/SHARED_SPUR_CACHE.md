# Persistent and shared spur API cache ? 17 November 2026

Implemented successful-result caching for spur localization and geometry drafts. Image filenames, age labels and image ordering are not inputs. The identity includes EXIF-oriented RGB pixel SHA-256, image dimensions, requested task, model/failover selection, prompt hashes, preprocessing/encoding policy, Pillow version, output/thinking parameters and retry policy. Changing image pixels or these request settings creates a separate entry.

PostgreSQL stores the response and provenance, not the uploaded photo or API credential. Completed empty predictions are valid saved responses. HTTP failures, timeouts, malformed output and unconfigured requests are not saved as negative detections. Existing model weights, age estimates and source photographs are preserved. A unique constraint makes the first successful committed response authoritative for each account/key/authority; concurrent callers return that winning response.

## One-time account connection

1. Sign in to your Render account and open `/rooster-age-estimator/shared-cache/`. Click **Create / replace service token**. Copy the token privately; it is shown once.
2. Sign in to the intended localhost account and open the same page on `http://127.0.0.1:8000`. Paste the token into **Service token from your Render account** and click **Verify and connect**.
3. Run a full analysis. Localhost first requests the Render account's saved result. On a miss, it sends exact oriented pixels as a lossless PNG; Render computes and persists a successful result. Subsequent analyses in either connected account reuse that result.

This explicit pairing proves access to both accounts; matching email addresses alone do not link users. The implementation does not claim the actual user's accounts are paired before this step. Existing successful results from the older in-memory cache are not silently imported as server-verified predictions. Cache entries start with the upgraded workflow.

The Render service is authoritative and never connects back to itself. Localhost retains a copy of successfully shared responses. During a network/service outage it can reuse a previously shared copy with the exact same identity. Without such a copy it reports an explicit service failure and does not independently call Gemini and create a divergent shared result. A rejected/revoked token does not authorize use of a local shared copy. On reconnection, the service's canonical result wins.

## Authentication and privacy

Service routes require a 256-bit bearer token and accept POST only. Normal session cookies alone do not authorize them. Every lookup is scoped to the token owner; there is no cache listing or arbitrary client-result import endpoint. The service validates uploaded pixels and recomputes the request identity. A mismatch returns HTTP 409.

Tokens are stored as SHA-256 hashes on the service. The desktop connection token is encrypted with Fernet using a key derived from the local Django secret key; it is not returned in subsequent pages or API responses. Pairing and token issue/revoke actions require login and CSRF protection. Rotating/revoking a service token invalidates old clients. If the local Django secret key changes, reconnect the client. The HTTPS service host is allowlisted, credentials/query strings in URLs are rejected, and HTTP redirects are disabled to prevent forwarding authorization to another host. HTTP localhost exceptions exist only in explicit test settings.

No new billing plan or model training is introduced. The first uncached API request still depends on provider availability, credentials and quota. Sharing does not make a wrong model prediction correct, nor does it guarantee the same result after changing request/model settings. Cached geometry remains an unverified API draft; physical length still requires a reviewed outline/endpoints and a known scale.

## Database rollout

Migration `core.0012_spur_prediction_cache` adds three tables: successful predictions, hashed service credentials, and encrypted client connections. It does not delete or replace existing account or estimate tables. The desktop migration was executed successfully. Render's existing startup migration applies it on deployment.

Dependency added: `cryptography==46.0.3`, for standard Fernet encryption. It is imported only when managing/using a client connection.

## Executed verification

- 73 targeted Django tests passed, including existing estimator behavior, owner isolation, cache hits, successful empty responses, failed-request non-caching, geometry drafts, identity invalidation, concurrent-writer result selection, bearer-only access, CSRF, revocation, unsafe URL rejection, shared cache misses, network outages and encrypted pairing.
- A genuine API result on the existing 300 ? 300 full-chicken photograph was saved in the actual desktop PostgreSQL database. A separate process then retrieved the same spur box `[148.5, 202.5, 183.0, 223.5]` with API computation blocked. The existing saved estimate remained unchanged.
- An actual browser pairing test used two isolated app/database instances. A service token was created through the CSRF-protected UI, pasted into the client UI and verified over HTTP under explicit test-only settings. A real external API response was shared. The service process was then restarted with all API computation blocked: the same box was returned from persistent storage. Anonymous access returned 401; there were no JavaScript errors. No production accounts or synthetic training labels were created by this test.

Machine-readable results are in `reports/measurement/persistent_cache_postgres_verification.json` and `shared_cache_browser_verification.json`.
