FROM rust:latest
RUN rustup install nightly
# RUN rustup default nightly
# We need this to get JSON output from cargo criterion
RUN cargo install cargo-criterion
ENV RUSTFLAGS="-C target-cpu=native"
ENV CARGO_TERM_COLOR="never"
ENV TERM="dumb"
VOLUME /app
WORKDIR /app

CMD ["echo ERROR"]