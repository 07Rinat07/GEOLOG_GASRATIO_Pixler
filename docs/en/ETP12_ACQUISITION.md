# ETP 1.2 ChannelData acquisition

Version 0.7.82 converts reviewed ETP ChannelData into immutable normalized measurement batches and append-only AcquisitionSession records.

## Stable identity

ETP numeric channel IDs are valid only inside one negotiated session and may change after reconnect. Mapping, semantic identity and deduplication therefore use the Channel URI. Every incoming batch carries the current `channel_id -> URI` map and the subscription generation. Metadata fingerprints exclude transient IDs, generation counters and sample statistics.

## Import Review

`Etp12DiscoveryAccumulator` combines ChannelMetadata with observed sample statistics. Import Review confirms scalar numeric channels, canonical mnemonics, semantic kinds, quantity classes, source and target UOM, and the active time or depth index. Commit produces an immutable `AcquisitionDatasetSchema`; a metadata-surface change invalidates the old review.

## Normalization

`Etp12ChannelNormalizer` groups points by canonical index, converts ETP microsecond timestamps to Unix nanoseconds and applies only explicit UOM conversions. Each row contains the exact curve set declared by the schema, while unavailable values are represented as null and become NaN in the growing Dataset. Invalid indexes or nonnumeric values remain structured diagnostics.

## Reconnect overlap

Every accepted point receives a stable SHA-256 identity over schema digest, Channel URI, normalized index and normalized value. A bounded deduplication window removes exact overlap after subscription restoration even when numeric channel IDs have changed. A changed value at the same index remains new append-only data. Point hashes are written to AcquisitionRecord provenance.

## Runtime and recovery

`Etp12AcquisitionRuntime` provides bounded enqueue, atomic multi-row insertion, configurable backpressure, periodic checkpoints and controlled close. Open sessions can be reconstructed after project reload once current ChannelMetadata is available. The recent deduplication window is rebuilt from persisted provenance. Project format remains v20.
