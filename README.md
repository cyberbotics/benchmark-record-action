# Benchmark Record Action

This composite action is to be used with Webots Benchmarks.
It records an animation and the performance of a competitor in a benchmark and push the changes to GitHub.
For more information on Webots Benchmarks please refer to the template benchmark [here](https://github.com/cyberbotics/benchmark-template/blob/main/README.md).

## Inputs

This composite action works with environment variables as inputs:

- INPUT_INDIVIDUAL_EVALUATION: the competitor's line from `competitors.txt`. Each line in `competitors.txt` file has the following format: `id*:controller_repository_path*:performance:performance string:date` where * fields are mandatory
- INPUT_PUSH_TOKEN: token used to push results to current repository, typically the default GITHUB_TOKEN
- INPUT_FETCH_TOKEN: token used to fetch the competitor repository, typically REPO_TOKEN. A more privileged token than GITHUB_TOKEN is needed to fetch controllers from private repositories.

## Python code pipeline

First, the `webots.yml` file is parsed to get several benchmark parameters. Then the script performs the following steps:

### 1. Get competitors

We parse the `INPUT_INDIVIDUAL_EVALUATION` environment variable to get the **id** and the **controller repository** needed for the rest of the code.

### 2. Clone the competitor repositories

We clone the competitor's **repository** into the Benchmark's `controllers/` directory and rename them as: `competitor_{id}_{username}/` .
> the `{username}` variable is obtained from the **controller repository**

### 3. Run Webots and record Benchmarks

We create a temporary storage directory `/tmp/animation` and modify the world file to add a `Supervisor` running the `animator.py` controller and we set the robot's controller to \<extern\>.

We then build Webots and the competitor's controller inside Docker containers. We first launch Webots and when it is waiting for a connection of an external controller, we launch the controller container.

The animator records and saves the animation files and the benchmark performance into the temporary storage.

The animation files are renamed as `animation.json` and `scene.x3d` files and are moved to their own directory `storage/wb_animation_{id}`. If there is an old animation, it gets overwritten.
The `competitors.txt` file is also updated with the new recorded performance.

### 4. Remove temporary files

We remove the various temporary files so that only the updated files of interest are left.

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
    INPUT_FETCH_TOKEN: ${{ secrets.REPO_TOKEN }}
    INPUT_PUSH_TOKEN: ${{ github.token }}
```
