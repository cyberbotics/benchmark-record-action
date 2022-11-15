# Benchmark Record Action

This action is to be used with Webots Benchmarks.
It records animations and saves the performance of each competitor in the benchmark.
For more information on Webots Benchmarks please refer to the template benchmark [here](https://github.com/cyberbotics/robot-programming-benchmark/blob/main/README.md).

## Inputs

This composite action works with environment variables. It expects several input environment variables:

- INPUT_INDIVIDUAL_EVALUATION: the competitor's line from `competitors.txt`. Each line in `competitors.txt` file has the following format: `id*:controller_repository_path*:performance:performance string:date` where * fields are mandatory
- DEFAULT_CONTROLLER: name of the default controller used by the benchmark
- INPUT_FETCH_TOKEN: token used to fetch the competitor repository, typically REPO_TOKEN
- INPUT_PUSH_TOKEN: token used to push results to current repository, typically GITHUB_TOKEN

## Pipeline

After checking out the repository to get access of the Benchmark's files, the action performs the following steps:

### 1. Get competitors

We parse the `INPUT_INDIVIDUAL_EVALUATION` environment variable to get the **id** and the **controller repository** needed for the rest of the code.

### 2. Clone the competitor repositories

We clone the competitor's **repository** into the Benchmark's `controller/` directory and rename them as: `competitor_{id}_{username}/` .
> the `{username}` variable is obtained from the **controller repository**

### 3. Run Webots and record Benchmarks

We create a temporary storage directory `/tmp/animation` and modify the world file to add `Supervisor` running the `animator.py` controller and set the robot's controller to \<extern\>. We then build Webots and the competitor's controller inside Docker containers. We first launch the Webots container and when it is waiting for the external controller we launch the controller container.

The animator records and saves the animation files and the benchmark performance into the temporary storage.

The animation files are renamed as `animation.json` and `scene.x3d` files and are moved to their own directory `storage/wb_animation_{id}`.
The `competitors.txt` file is also updated with the new recorded performances.

### 4. Remove temporary files

### 5. Commit and push updates

All of the updates are committed and pushed to the Benchmark's repository.
The modified directories and files are therefore:

- `competitors.txt`
- `storage/wb_animation_{id}`

## Workflow

Here is a GitHub workflow snippet which uses the composite action:

```yaml
- name: Record and update Benchmark animations
  uses: cyberbotics/benchmark-record-action@dockerContainers
  env:
    INPUT_INDIVIDUAL_EVALUATION: "12:username/repoName"
    DEFAULT_CONTROLLER: edit_me
    INPUT_FETCH_TOKEN: ${{ secrets.REPO_TOKEN }}
    INPUT_PUSH_TOKEN: ${{ github.token }}
```
