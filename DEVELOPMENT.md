# Development Guidelines

## Local Development
Build:
```bash
docker build . -t benchmark-record-action
```

### Benchmark

Pull a sample project:
```bash
git clone https://github.com/cyberbotics/robot-programming-benchmark.git $HOME/robot-programming-benchmark
```

Run:
```bash
docker run \
    -v $HOME/robot-programming-benchmark:/root/repo \
    -w /root/repo \
    -e DEBUG=true \
    -it benchmark-record-action
```
