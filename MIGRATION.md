# Migration notes

## 2026-09: rebased onto upstream v3

This fork was rebased onto `d3i-infra/data-donation-task`'s `development` branch
(v3, config-driven platform extraction) in September 2026, with the education-fork
work re-applied on top — see the "Education fork (2026-09)" section of
[CHANGELOG.md](CHANGELOG.md) for the list of stories that were carried across.

Before `master` is force-pushed to the accepted branch, the old `master` head is
tagged `pre-v3-education`, so the fork's pre-rebase history — everything that
came before this rebase — stays reachable even after `master` moves:

```sh
git tag pre-v3-education "$(git rev-parse master)"
git push origin pre-v3-education
```

Verify the tag exists with `git tag -l pre-v3-education`. Once it's pushed, any
commit or file from the old fork can still be found there
(`git show pre-v3-education:<path>`).
