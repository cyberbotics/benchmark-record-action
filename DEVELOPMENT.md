# Development Guidelines

## Local Development
Build:
```bash
docker build . -t competition-record-action
```

### Competition

Pull a sample project:
```bash
git clone https://github.com/cyberbotics/robot-programming-competition.git $HOME/robot-programming-competition
```

Run:
```bash
docker run \
    -v $HOME/robot-programming-competition:/root/repo \
    -w /root/repo \
    -e DEBUG=true \
    -it competition-record-action
```
