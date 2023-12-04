from rust:latest
RUN rustup install nightly
RUN rustup default nightly
ENV RUSTFLAGS="-C target-cpu=native"
ENV CARGO_TERM_COLOR="never"
ENV TERM="dumb"

# These should be cached
WORKDIR /usr/src/ferris-elf
COPY Cargo.toml Cargo.toml
COPY src/main.rs src/main.rs
COPY src/placeholder.rs src/lib.rs
RUN cargo build --release
RUN cargo clean -p ferris-elf

# For each build
COPY src/code.rs src/lib.rs
RUN touch src/lib.rs
RUN cargo build --release

CMD ["echo ERROR"]