# Qdrant

Qdrant is an open-source vector database and similarity-search engine. It stores
high-dimensional vectors together with a JSON payload and lets you search by nearest
neighbour.

## Distance metrics

Qdrant supports Cosine, Dot product and Euclidean distance. This portfolio configures
collections with **Cosine** distance, which is a robust default for normalized text
embeddings.

## Collections

A collection is a named set of points. Each point has an id, a vector, and an optional
payload. Vector size and distance metric are fixed when the collection is created.

## Filtering

Searches can be combined with payload filters (for example, restrict results to a single
`source` file). Qdrant evaluates filters together with the vector search, so filtered
queries stay fast.

## Running locally

Qdrant ships as a Docker image. The REST API and web dashboard are served on port 6333,
and gRPC on port 6334. Data is persisted to disk so restarts keep your collections.
