# ADR-0009 — Local vehicle speed stays out of the weapon rules

- Decision ID: ADR-0009
- Date: 2026-11-10
- Status: accepted

## Context

On-foot speed is 5 and the pistol and rifle values live in `app/game/items.py`. The live match had no vehicle. Those numbers are this server's rules, not original Rules of Survival data.

## Problem

A vehicle needs a speed without changing weapon damage or the on-foot movement that the scenario already checks.

## Options considered

- Leave vehicles unimplemented.
- Add a development buggy whose speed is used only while a player has boarded it.

## Chosen solution

`VEHICLES["buggy"]` has speed 12 and one seat. `board` and `exit` are actions on the existing JSON protocol. A boarded player moves at that speed and cannot shoot. Leaving the vehicle restores speed 5. Two vehicles are placed per match from a separate random stream so the loot stream stays unchanged.

## Reason

The scenario asserts a movement delta of 5. Vehicle speed must not apply unless the player boards.

## Consequences

This is not an original vehicle table. Equipment is still not equipped. Match results still record placement and kills, not experience or currency.

## Related tasks

RO-050

## Related changes

CH-0007
