# Rater instructions: SupportBench and ContentBench

Listener-task version: 1.0.0. Exact questions and descriptions are in
[listener_tasks.json](../configs/listener_tasks.json).

## Your task

You will hear two audio clips of the same script, labeled A and B. Rate which one you would prefer for the context named in the question.

SupportBench asks about a customer-support conversation. ContentBench asks about narrated articles, stories, and videos.

## The scale

| Score | Meaning |
|---|---|
| −2 | A is much worse than B |
| −1 | A is worse than B |
| 0 | About the same |
| +1 | A is better than B |
| +2 | A is much better than B |

## What to listen for

Make one overall preference judgment for the named context.

1. For SupportBench, consider how easy the response is to understand, how natural it sounds, and how well it fits a customer-support call.
2. For ContentBench, consider how easy the passage is to follow, how natural it sounds, and how well its pacing and expression fit narration.
3. Make one overall preference judgment. There is no separate reading-accuracy score or rule that correctness automatically determines the preferred recording.

Keep the volume fixed once it is set.

## How to work

- Listen to both clips fully at least once before rating. Replaying is encouraged.
- Use 0 honestly when you genuinely can't hear a difference — forced preferences add noise.

## Environment

Use headphones in a quiet room. The linked listener-task file defines the instructions sent to the platform; it does not specify additional calibration or attention-check tasks.
