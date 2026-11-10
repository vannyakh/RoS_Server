# Database relationships

```text
Account
  └── Player
       ├── PlayerStatistics
       ├── PlayerProgression
       ├── PlayerInventory
       │    └── InventoryItem ── ItemDefinition
       ├── PlayerCurrency
       ├── LobbyMember ── Lobby
       ├── TeamMember ── Team ── Lobby
       └── MatchParticipant ── Match
            └── MatchResult

GameMode ── Match
MapDefinition ── Match
Match ── MatchStatistics
```

Account to player is one-to-one (`players.account_id` is unique). Nickname is unique across profiles. Deleting an account cascades to its player, statistics, inventory, currency, sessions, and devices. Login history keeps the row and sets `account_id` to null.

Item, mode, and map rows are restricted: a definition that is still referenced cannot be deleted. Match participants and results cascade with the match. A player can appear only once in a match, once in a lobby, and once on a team inside that lobby.

Relationships are `lazy="raise"`. Repositories load a collection only for the query that needs it. The game tick does not traverse these relationships.
