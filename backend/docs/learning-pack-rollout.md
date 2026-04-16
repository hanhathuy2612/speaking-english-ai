# Learning Pack Rollout Checklist

## Objective

Roll out topic learning packs safely while keeping conversation quality stable for all topics.

## Phase 1 - Infrastructure (done in this change set)

- Add `learning_pack_json` to `topics` and `topic_units`.
- Add admin CRUD endpoints for topic/unit learning packs.
- Add learner endpoint to resolve effective pack with fallback.
- Inject compact learning-pack context into opening message prompts.

## Phase 2 - Content seeding

- Pick top 10 highest-friction topics from product analytics.
- For each topic, add:
  - 15-20 vocabulary entries
  - 8-10 sentence patterns
  - 5-8 idea prompts
  - 3-5 common mistakes
  - 1-3 model responses
- For each guided unit with high drop-off, add a unit-specific pack overriding topic defaults.

## Phase 3 - Monitoring

- Track:
  - turn-1 dropout rate
  - average user answer length
  - number of retries/reworks
  - session completion rate per topic/unit
- Review weekly and improve low-performing packs.

## QA checklist

- Topic with unit pack returns source `unit`.
- Topic without unit pack but with topic pack returns source `topic`.
- Topic with no authored pack returns source `fallback`.
- Opening assistant message remains generated when packs are empty/invalid.
