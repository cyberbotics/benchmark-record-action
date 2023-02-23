# Competition Record Action

This composite action is to be used with Webots competitions.
It records an animation and the performance of a participant in a competition. An optional setting can be set to push the changes to GitHub at the end of the evaluation.
For more information on Webots competitions please refer to the competition template [here](https://github.com/cyberbotics/competition-template/blob/main/README.md).

## Input

This composite action works with environment variables as input, two mandatory and one optional:

### Mandatory Input

| Name | Description | Required | Default |
| --- | --- | --- | --- |
| `participant_repo_id` | The ID of the participant repository | true |  |
| `participant_repo_name` | The name of the participant repository | true |  |
| `participant_repo_private` | Whether the participant repository is private | true |  |
| `log_url` | The URL of GitHub action logs | true |  |
| `repo_token` | The GitHub token | true |  |
| `upload_performances` | Whether to upload the performances to the cloud | false | `false` |

<!--
- INPUT_INDIVIDUAL_EVALUATION: information about the repository of the participant with the following format: `id:repository:private`, e.g., `348767863:omichel/my-competitor:true`.
- INPUT_REPO_TOKEN: token used to fetch the participant repository, typically REPO_TOKEN. A more privileged token than GITHUB_TOKEN is needed to fetch controllers from private repositories.
-->

### Optional Input

- INPUT_ALLOW_PUSH: allows the action to push the modified files after the evaluation using the INPUT_REPO_TOKEN.

## Python Code Pipeline

First, the `webots.yml` file is parsed to get several competition parameters. Then the script performs the following steps:

### 1. Get the Participants

We parse the `INPUT_INDIVIDUAL_EVALUATION` environment variable to get the **id**, the **controller repository** and the **private** status needed in the rest of the code.

### 2. Clone the Participant Repositories

We clone the participant **repository** into the competition `controllers/` directory and rename it using the GitHub repository: `{id}`.

### 3. Run Webots and Record Animations

We create a temporary storage directory `/tmp` and modify the world file to add a `Supervisor` running the `animator.py` controller and we set the robot's controller to \<extern\>.

We then run Webots and the controller of the participant inside Docker containers. We first launch Webots and when it is waiting for a connection of an external controller, we launch the controller container.

The animator records and saves the animation files and the competition performance in the temporary storage.

The animation files are renamed as `animation.json` and `scene.x3d` files and are moved to their own directory `storage/wb_animation_{id}`. If there is an old animation, it gets overwritten.
The `participants.json` file is also updated with the new recorded performance.

### 4. Remove temporary files

We remove the various temporary files so that only the updated files of interest are left.

### 5. Commit and push updates (if INPUT_ALLOW_PUSH is set)

All of the updates are committed and pushed to the repository of the competition organizer.
The modified directories and files are therefore:

- `participants.json`
- `storage/wb_animation_{id}`

## Workflow

Here is a GitHub workflow snippet which uses the composite action:

```yaml
- name: Record and update animations
  uses: cyberbotics/competition-record-action@main
  env:
    INPUT_INDIVIDUAL_EVALUATION: "1876568742:username/repository_name:true"
    INPUT_REPO_TOKEN: ${{ secrets.REPO_TOKEN }}
    INPUT_ALLOW_PUSH: True
```
