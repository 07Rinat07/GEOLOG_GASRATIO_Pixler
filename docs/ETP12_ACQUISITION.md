# ETP 1.2 ChannelData acquisition

Version 0.7.82 converts reviewed ETP ChannelData into immutable normalized measurement batches and
append-only AcquisitionSession records.

## Stable identity

ETP numeric channel IDs are scoped to one negotiated session and may change after reconnect. Mapping,
semantic identity and deduplication therefore use the Channel URI. Each incoming batch carries the
current `channel_id -> URI` map and subscription generation.

## Import Review

`Etp12DiscoveryAccumulator` combines ChannelMetadata and observed samples. The deterministic
fingerprint excludes transient channel IDs, generation numbers and sample counters. Import Review
selects numeric channels, semantic bindings, canonical mnemonics, quantity classes, index contract and
source/target UOM. Commit creates an immutable `AcquisitionDatasetSchema`.

## Normalization

`Etp12ChannelNormalizer` groups points by canonical index, converts ETP microsecond timestamps to Unix
nanoseconds and applies explicit UOM conversions. Rows always contain the exact curve set declared by
the schema; absent values are stored as null/NaN.

## Reconnect overlap

Every accepted point receives a stable SHA-256 identity over schema digest, channel URI, normalized
index and normalized value. A bounded deduplication window removes exact overlap after subscription
restore even when server channel IDs change. Changed values at the same index remain append-only data.
Point hashes are recorded in AcquisitionRecord provenance and restored after project reload.

## Runtime

`Etp12AcquisitionRuntime` provides bounded enqueue, atomic multi-row insertion, backpressure policy,
periodic checkpoints, controlled close and open-session resume. Project format remains v20.
