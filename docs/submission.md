# Submission kit

## Project copy

**Name:** Delhi Air Window

**One sentence:** A Fetch.ai agent that finds a better 1–2 hour outdoor window in Delhi NCR using live AQI, PM2.5, rain and heat forecasts.

**Target users:** Runners, cyclists, parents and commuters in Delhi NCR; it also works with city names worldwide. Other planning agents can hire it through a typed protocol.

**Problem:** A current AQI number does not tell someone when to go outside. The agent compares future consecutive hours, explains the trade-offs, and flags when even the best slot has unhealthy air.

**Origin:** Ported from BLR Air Window, built for Stranger Builds Bangalore 2026. Licence: MIT; Open-Meteo/CAMS attribution is in both READMEs.

## Ten evaluation prompts

1. Best 1-hour window to run in Hauz Khas.
2. Best 2-hour cycling window in Dwarka.
3. When is the air cleanest in Noida?
4. Can I take kids outside in Saket tomorrow morning?
5. Best time to commute in Okhla today.
6. Walk near India Gate tomorrow evening.
7. Compare Gurgaon and Noida for a run tomorrow morning.
8. Best 2-hour walk in Melbourne, Australia.
9. Run in no-such-place-xyz.
10. Best 3-hour running window in Delhi.

Success means a useful typed answer or an honest unsupported/location/no-window error, not an invented forecast. Local CLI tests do not count as an Agentverse evaluation or an outside-user try.
