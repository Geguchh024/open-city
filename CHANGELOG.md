# Changelog

## 0.3.0

- Moving traffic: cars drive round closed loops in the right-hand lanes, animated by the scene clock
  (`OC Traffic`). Block loops turn right at every corner and one loop runs round the outer lanes, so no
  two loops cross. New *Traffic Speed* setting. Narrow streets park on one side only, and the lanes and
  centre lines shift over to leave room for two lanes of traffic.
- Night: *Tools > Night* gives a moonlit sky with stars, lit windows, glowing signs and tail lights, real
  street and park lamp lights and headlights (instanced from shared lights, so the whole town switches
  at once), AgX and a bloom. *Day* switches it all back.
- Surroundings: the town no longer ends in a void. *Hills & Forest* (the default) sets it in a valley of
  wooded hills, *Forest* rings it with woods, *Open* gives fields to the horizon. The diorama base is now
  off by default and, when on, carries the countryside to its rim.

## 0.2.0

A redesign: Open City now generates stylized small towns from a modular architectural kit instead of
grey metropolis blocks.

- Modular building kit: sash, arched and wide windows, French doors, storefronts, shop and front
  doors with stoops, shutters, flower boxes, three balcony styles, awnings, fascias with raised
  lettering, plinths, belt courses, dentil cornices, string courses, quoins and pilasters.
- Parametric buildings: bays wide and deep, floors, bay width, floor and ground-floor height; resizing
  rearranges modules instead of stretching them. Party walls, corner facades, entrance bay.
- Roofs: parapet, flat, gable, hip and mansard with dormers, chimneys and rooftop equipment; corner
  turrets and clock towers.
- Small-town layout: kerbed blocks with rounded corners, a main street, corner buildings, shop rows,
  townhouses, detached houses with gardens, parks with paths and a fountain, alleys.
- Rule-based props: street lights, trees with grates, benches, bins, hydrants, mailboxes, bollards,
  stop and street signs, traffic lights, a bus shelter, bike racks, cafe tables, sandwich boards,
  planters, hedges, fences, flower beds and parked or moving cars.
- Road markings, zebra crossings, stop lines, parking bays and manholes; an optional diorama base.
- Attribute-driven stylized materials and colour schemes; a *Sun & Sky* stage.
- One object per building with live settings, re-roll and lock; town settings with live update.
- 5 presets: Main Street, Old Quarter, Garden Suburb, Brick Town, Market Town.
- Removed: the metropolis layouts (organic, radial), zoning by density and custom kit collections.
  Files made with 0.1 keep working, because their node groups are saved in the file.

## 0.1.0

First release: a real-time Geometry Nodes city generator.
