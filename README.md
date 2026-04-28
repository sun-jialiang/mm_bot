# mm_bot

A bot that posts the daily lunch menu to Mattermost.

## Scheduling

The workflow is triggered via `workflow_dispatch` rather than a GitHub `schedule` cron, because scheduled workflows are subject to GitHub's shared runner queue and can be delayed by hours during peak times.

To trigger the workflow on a reliable schedule, use an external cron service such as [cron-job.org](https://cron-job.org) or [EasyCron](https://www.easycron.com):

1. Create a GitHub **Fine-grained Personal Access Token** (or classic PAT) with **Actions: write** permission scoped to this repository.

2. In your cron service, create a job with the desired schedule (e.g. `37 7 * * 1-5` in your local timezone) that sends:

   - **Method:** `POST`
   - **URL:** `https://api.github.com/repos/sun-jialiang/mm_bot/actions/workflows/menu_post.yml/dispatches`
   - **Headers:**
     ```
     Accept: application/vnd.github+json
     Authorization: Bearer <YOUR_PAT>
     X-GitHub-Api-Version: 2022-11-28
     ```
   - **Body:**
     ```json
     {"ref": "main"}
     ```

GitHub treats `workflow_dispatch` as a user-initiated run and schedules it immediately, bypassing the shared scheduler queue.