# Competition Record Action

This is a composite action designed to be used with Webots competitions. It records a participant's performance in a competition, as well as an animation of the participant's robot in action. This action is able to detect whether the GitHub runner being used is capable of GPU acceleration (e.g. if using a self-hosted runner). Additionally, there is an optional setting that allows for the changes to be pushed to webots.cloud at the end of the evaluation.

For more information on Webots competitions please refer to the competition template [here](https://github.com/cyberbotics/competition-template/blob/main/README.md).

## Inputs

### Mandatory

| Name | Description |
| --- | --- |
| `participant_repo_id` | The ID of the participant repository |
| `participant_repo_name` | The name of the participant repository |
| `participant_repo_private` | Whether the participant repository is private |
| `log_url` | The URL of GitHub action logs |
| `repo_token` | Token used to fetch the participant repository, typically REPO_TOKEN |

Note that a more privileged token than `GITHUB_TOKEN` is required to fetch controllers from private repositories.

### Optional

| Name | Description | Default |
| --- | --- | --- |
| `upload_performances` | Whether to upload the performances to the cloud | `false` |

## Python Code Pipeline

First, the competition's `webots.yml` file is parsed to get several competition parameters. It then detects if the GitHub runner has GPU capabilities. Finally the script performs the following steps:

### 1. Fetch the participant's controller

A `Participant` class is defined to store all the information about a participant and to download its controller files.
The controller to be tested is initialized using the `participant_repo_id`, `participant_repo_name` and `participant_repo_private` inputs.

### 2. Run Webots and Record Animations

We create a temporary storage directory `/tmp` and modify the world file to add a `Supervisor` running the `animator.py` controller and we set the robot's controller to \<extern\>.

We then run Webots and the participant's controller inside Docker containers. We first launch Webots and when it is waiting for a connection of an external controller, we launch the controller container.

The animator records and saves the animation files and the competition performance in the temporary storage.

If the competition is in a tournament format, the controller keeps on duelling the controller above it in the ranking until it loses in a bubble-sort logic.

The JSON animation file is renamed as `animation.json` and is moved to a directory `storage/{id}`.
The `participants.json` file is also updated with the new recorded performance.

### 3. Upload performances to webots.cloud (if UPLOAD_PERFORMANCES is set)

If `UPLOAD_PERFORMANCES` is set, `animation.json` and the updated `participants.json` are uploaded to webots.cloud.

## Workflow

Here is a GitHub workflow snippet which uses the composite action:

```yaml
- name: Record and update animations
  uses: cyberbotics/competition-record-action@main
  with:
    participant_repo_id: ${{ env.PARTICIPANT_REPO_ID }}
    participant_repo_name: ${{github.event.client_payload.repository}}
    participant_repo_private: ${{env.PARTICIPANT_REPO_PRIVATE}}
    log_url: ${{ env.LOG_URL }}
    repo_token: ${{ secrets.REPO_TOKEN }}
    upload_performances: false
```
