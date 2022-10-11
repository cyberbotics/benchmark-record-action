# Benchmark Record Action

This action is to be used with Webots Benchmarks.
It records animations and saves the performance of each competitor in the benchmark.
For more information on Webots Benchmarks please refer to the template benchmark [here](https://github.com/cyberbotics/robot-programming-benchmark/blob/main/README.md).


## Pipeline

After checking out the repository to get access of the Benchmark's files, the action performs the following steps:

### 1. Get competitors

Here we read the `competitors.txt` file located at the root of the Benchmark repository to get, for each competitor, an **id** and a **controller repository**.
Each line in `competitors.txt` file has the following format: `id*:controller_repository_path*:performance:performance string:date`
> \* obligatory fields

### 2. Clone the competitor controllers

We clone the **controller folder** of each competitor using subversion into the Benchmark's `controller/` directory and rename them as: `competitor_{id}_{username}/competitor_{id}_{username}.py` .
> the `{username}` variable is obtained from the **controller repository**

### 3. Run Webots and record Benchmarks

We create a temporary storage directory `/tmp/animation`. After opening an instance of Webots, we run the Benchmark world with an added `Supervisor` running the `animation_recorder.py` controller.
This controller loops through the competitor controllers and runs a simulation for each.
During each run, the controller records and saves the animation files and benchmark performance into the temporary storage.

The animation files are renamed as `animation.json` and `scene.x3d` files are moved to their own directory, `storage/wb_animation_{id}`, for each controller in the Benchmark's repository.
The `competitors.txt` file is also updated with the new recorded performances and the temporary directories and files are deleted.

### 4. Remove competitor controllers

We remove the competitor controllers previously cloned from the Benchmark's repository.

### 5. Commit and push updates

All of the updates are commited and pushed to the Benchmark's repository.
The modified directories and files are therefore: 
  * `competitors.txt`
  * `storage/wb_animation_{id}`


## Workflow

Here is a GitHub workflow snippet which uses the action:
```yaml
name: Record animation

jobs:
  record:
    runs-on: ubuntu-latest
    steps:
      - name: Check out the repo
        uses: actions/checkout@v2
      - name: Record and deploy the animation
        uses: cyberbotics/webots-animation-action@master
        env: 
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```
> You can save the snippet to e.g.: `.github/workflows/benchmark_record.yml` at the root of your benchmark repository.

## Limitations

Benchmark success confirmation is currently defined by a message sent by the Benchmark Supervisor to the animation recorder via a an emitter/receiver pair.
The confirmation of success would be better and more secure by passing throught the Benchmark Supervisor's Robot Window, before being transmitted to the animation recorder.
However Opening a browser window has not proven to work sufficiently within this Action, therefore it cannot be relied on.
Therefore, currently, the Benchmark Supervisor communicates directly to the animation recorders Supervisor without this confirmation.
This means that any competitor controller can use an emitter with the same channel as the receiver to communicate a Benchmark perfomance message, therefore allowing them to cheat.

A solution to avoid this would be to run the competitor controllers in their own Docker container as Extern controllers, isolating them from the file system.
We could then combine the animation recorder Supervisor and the Benchmark Supervisor into one, and allow file modifications from there.
