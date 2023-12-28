FROM rust:latest
VOLUME /app/src
VOLUME /app/benches
VOLUME /app/inputs
VOLUME /app/target
WORKDIR /app
# RUN rustup default nightly
ENV RUSTFLAGS="-C target-cpu=native"
ENV CARGO_TERM_COLOR="never"
ENV TERM="dumb"

COPY Cargo.lock Cargo.toml crate-information.json crate-modifications.toml /app/
RUN mkdir -p /app/benches && mkdir -p /app/src && touch /app/benches/bench.rs && touch /app/src/lib.rs && rustup install nightly && cargo install cargo-criterion && cargo vendor && mkdir -p /app/.cargo/
COPY extra-cargo.toml /app/.cargo/config.toml

CMD ["echo ERROR"]