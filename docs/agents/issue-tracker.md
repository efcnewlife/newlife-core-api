# Issue tracker: GitHub + Linear

Create issues and specs in the owning GitHub repository via `gh`. After synchronization, use Linear team `EFC` for all issue reads, updates, comments, dependencies, and workflow states.

GitHub hosts code and pull requests. Use `gh` for PR operations.

## Auth

- Linear endpoint: `https://api.linear.app/graphql`
- Header: `Authorization: $LINEAR_API_KEY`
- Do not print the key. Resolve `EFC` with `teams(filter: { key: { eq: "EFC" } })`.

## Repository and Project

Resolve the owning GitHub repository from the task and verify it against `git remote -v`. Pass `--repo <owner/repo>` explicitly when creating issues.

Default Linear Project for this repo: **`newlife core api`**.

Resolve it with `projects(filter: { name: { eq: "newlife core api" } })`. After synchronization, set the synced issue's `projectId` using `issueUpdate`.

## Conventions

- **Create**: `gh issue create --repo <owner/repo> --title "..." --body-file <path>`. Write the Markdown body to a file; include initial labels with `--label`.
- **Sync**: wait for the integration to create the Linear issue. Match it by the exact GitHub issue URL in its attachments. If no unique match is found, report the synchronization blocker; do not create another issue in either tracker.
- **Read**: `issue(id: "EFC-123")` with `id`, `identifier`, `title`, `description`, `project { id name }`, `state { name type }`, labels, comments, and attachments. Include parent, children, and blocking relations when relevant.
- **List**: `issues(filter: { team: { key: { eq: "EFC" } }, state: { type: { nin: ["completed", "canceled"] } } })`. Add project, state, or label filters required by the task.
- **Update**: `issueUpdate` for title, description, assignee, project, parent, and workflow state.
- **Comment**: `commentCreate(input: { issueId, body })`. Use the synced thread when the comment must also appear in GitHub.
- **Apply / remove labels**: `issueAddLabel` / `issueRemoveLabel`. Resolve label ids by name; create missing labels on the team.
- **Close**: `issueUpdate` to the team's state whose `type` is `completed` (Done). For `wontfix`, comment first and use a state whose `type` is `canceled`. Let the integration reflect the result in GitHub.

Use the GitHub issue URL or `owner/repo#number` for repository identity, and `EFC-123` or the Linear issue UUID for Linear operations. Never assume their numbers match. Follow the repository's documented branch naming convention.

## Pull requests as a triage surface

**PRs as a request surface: no.**

For work completed by merging the PR, use `Closes EFC-<number>` and reference the GitHub issue URL without a closing keyword. Linear PR automation owns completion; issue sync reflects it in GitHub.

## When a skill says "publish to the issue tracker"

Create the issue in GitHub, resolve its synced Linear issue, then set its Project and any remaining metadata in Linear. Keep newly published specs and tickets in `Backlog`.

## When a skill says "fetch the relevant ticket"

Read the Linear issue, including comments and labels. If given a GitHub reference, first resolve its synced Linear issue.

## Wayfinding operations

Used by `/wayfinder`. Create the **map** and **child** issues through GitHub; manage their synced Linear issues afterward.

- **Map**: one issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body.
- **Child ticket**: create and resolve the synced issue, then set its Linear `parentId` to the map. Labels: `wayfinder:<type>` (`research` / `prototype` / `grilling` / `task`).
- **Blocking**: `issueRelationCreate` with type `blocks`. A ticket is unblocked when every blocker is completed or canceled. If relations are unavailable, put `Blocked by: EFC-n, EFC-n` at the top of the child description.
- **Frontier query**: the map's open Linear children, dropping any with an open blocker or an assignee. First in map order wins.
- **Claim**: `issueUpdate` assignee to the current Linear viewer (`viewer`). This is the claiming session's first write.
- **Resolve**: comment with the answer, set the Linear state to completed, then append a context pointer to the map's Decisions-so-far description.
