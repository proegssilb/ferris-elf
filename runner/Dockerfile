FROM rust:latest
VOLUME /app/src
VOLUME /app/benches
VOLUME /app/inputs
VOLUME /app/target
WORKDIR /app

# There's a github action that looks for this line specifically to set versions in the tags
# (since we can't use docker itself nor client libraries to fetch remote tags filtered by label)
LABEL bench_format="1"

ENV RUSTFLAGS="-C target-cpu=native"
ENV CARGO_TERM_COLOR="never"
ENV TERM="dumb"

COPY Cargo.lock Cargo.toml crate-information.json crate-modifications.toml /app/
RUN mkdir -p /app/benches && mkdir -p /app/src && touch /app/benches/bench.rs && touch /app/src/lib.rs && rustup install nightly && cargo install cargo-criterion && cargo vendor && mkdir -p /app/.cargo/
COPY extra-cargo.toml /app/.cargo/config.toml

CMD ["echo ERROR"]