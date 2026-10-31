# Submission kit

## Project copy

**Name:** BLR Air Window

**One sentence:** A Fetch.ai agent that finds a better 1–2 hour outdoor window using live AQI, PM2.5, rain and heat forecasts.

**Target users:** Runners, cyclists, parents and commuters in Bengaluru; also works with city names worldwide. Other planning agents can hire it through a typed protocol.

**Problem:** A current AQI or weather number does not tell someone when to go outside. The agent compares future consecutive hours, explains the trade-offs, and flags when even the best slot has unhealthy air.

**Fetch.ai integration:** uAgents mailbox, standard Agent Chat Protocol, optional ASI:One `asi1-mini` parsing, and a typed `blr-air-window` protocol with a separate caller demo.

**Original work:** New scoring, forecast adapters, parsing, localities, CLI, agent handlers and tests. The repository's research notes are local background; the code does not represent prior event entries. Licence: MIT; Open-Meteo/CAMS attribution is in both READMEs.

## Ten Agentverse Testing prompts

1. Best 1-hour window to run in HSR Layout.
2. Best 2-hour cycling window in Koramangala.
3. When is the air cleanest in Whitefield?
4. Can I take kids outside in Jayanagar tomorrow morning?
5. Best time to commute in Electronic City today.
6. Walk in Indiranagar tomorrow evening.
7. Best 2-hour walk in Melbourne, Australia.
8. Best time to run in New York, US tomorrow morning.
9. Run in no-such-place-xyz.
10. Best 3-hour running window in Bengaluru.

Success means a useful typed text answer or an honest unsupported/location/no-window error, not an invented forecast. Testing through the local CLI does not count as an Agentverse evaluation or an outside-user try.

## Routing experiment

Enable Agents in ASI:One. Try the ten prompts first without an @mention and then via the actual profile/handle. Record self-answer, other-agent routing, BLR Air selection, response and screenshot. Do not assume the requested handle has been claimed.

| Prompt | Agents on | Selected agent | Result | Evidence |
| --- | --- | --- | --- | --- |

## Two-minute demo script

- Explain the decision: when to run in HSR Layout, using live forecasts.
- In ASI:One, select the agent and ask for a one-hour run; point out the timezone, source and modelled-data caveat.
- Request two hours in Koramangala tomorrow morning to demonstrate constraints.
- Show the separate caller receiving a typed response.
- Show actual outside-test notes and their linked change, once collected.
- End on the real ASI:One share link and repository. Do not present a local demo as published proof.

## Three-to-five-minute Fetch.ai demo

Expand the short version with the Agentverse Active state, the Chat Protocol profile, the two-agent code path, missing-data handling and a real feedback-driven improvement. Use screen recording with `.env` and private keys closed. The repo and address must be visible.

## Proof checklist

- [ ] Public non-fork repository and creation timestamp satisfy the current rules.
- [ ] Actual stable agent address, Active dashboard and configured handle recorded.
- [ ] Agentverse README, description and avatar published.
- [ ] Ten or more real interactions; Agentverse Testing results captured.
- [ ] ASI:One chat and share link verified with Agents enabled.
- [ ] Three assigned outside-user tries in ASI:One, each with written note, score and sufficient duration.
- [ ] At least one shipped change traced to an actual note in [feedback.md](feedback.md).
- [ ] Actual aggregate counters and Discovery Insights recorded, with developer traffic disclosed.
- [ ] Short launch clip/post and separate Fetch.ai demo recorded; real URLs added to README.
- [ ] Event app fields and sponsor proof submitted; automatic completion actually confirmed.
- [ ] Fetch.ai Submission Agent acknowledgement obtained through the current official channel.
- [ ] Vote/share link copied from the event app; honest outreach only.
- [ ] Always-on process and same-seed migration verified for judging.

The source brief contains conflicting deadlines and try requirements. Verify current official rules in the event app; prepare three legitimate tries and both video lengths. This project deliberately does not claim those human/external actions are complete.
