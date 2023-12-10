FROM rust:latest
RUN rustup install nightly
RUN rustup default nightly
# We need this to get JSON output from cargo criterion
RUN cargo install --version=1.0.0-alpha3 cargo-criterion
ENV RUSTFLAGS="-C target-cpu=native"
ENV CARGO_TERM_COLOR="never"
ENV TERM="dumb"

# These should be cached
WORKDIR /usr/src/ferris-elf
COPY Cargo.toml Cargo.toml
COPY benches/bench.rs benches/bench.rs
COPY src/main.rs src/main.rs
COPY src/lib.rs src/lib.rs

# For each build
COPY src/code.rs src/code.rs
RUN touch src/lib.rs
RUN cargo build --release

CMD ["echo ERROR"]
