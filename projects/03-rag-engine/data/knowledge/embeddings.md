# Embeddings

An embedding is a dense numeric vector that represents the meaning of a piece of text.
Texts with similar meaning produce vectors that are close together in vector space, which
is what makes similarity search possible.

## Providers

This portfolio can generate embeddings with OpenAI (`text-embedding-3-small` by default)
or Google Gemini (`text-embedding-004`). The provider is selected by environment variable.
Anthropic does not offer an embeddings API, so when Anthropic is the chat provider the
system falls back to OpenAI embeddings.

## Dimensionality

Different embedding models produce vectors of different sizes. The vector store probes the
embedding model once to learn the dimension, then creates the Qdrant collection with that
exact size. Mixing embeddings of different dimensions in one collection is not allowed.
