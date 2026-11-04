# Ticket 10 implementation revision 1

Started 2026-11-05 after accepted environment integration `98fd8c4b`; stable 09
interface `4619dbfd` is consumed but remains subject to root acceptance. The
preparation `10-reserve-design.md` is retained as historical design. This revision
resolves its startup-power circularity before physical integration or run capture.

- UPS internal detection/transfer control is a separate actor from the main PLC.
  It receives explicitly allocated AC when available; otherwise it draws positive
  control power directly from finite UPS energy, independently of the protected
  output switch. Its room heat and battery depletion are accounted once.
- Generator local detection/control and cranking have a separately declared,
  finite starter/control energy store. Allocated AC can supply the controller;
  during black start it uses that store. Cranking/control dissipation leaves at
  the generator's outside boundary. An empty starter store prevents black start
  even with ample main fuel. After connection, allocated AC can sustain control;
  empty starter energy then prevents a later restart, not an already self-powered
  running engine. Running/starting idle fuel is separately positive and finite.
- The main PLC can accept backup-cooling commands only at a real powered local
  sample. No unsupplied main controller issues a new command. An already accepted
  physical selector may hold; newly requested changes need a powered actor.
- UPS protection remains controller/internal pump/intake pump only. The fan is
  paid AC after essential auxiliaries and before room/IT. Shared distribution
  failure gates all delivered paths, while finite internal actor energy may still
  be consumed in unsuccessful attempts.

Public behavior seams are independently varying reserve transitions, the paid
heat-exchange/electrical budget boundaries, and the agreed scenario/run/CLI.
Tests use literal independent budgets. Engineering attempts use fresh directories
and retain red results; they are not research trials or scientific-gain evidence.
