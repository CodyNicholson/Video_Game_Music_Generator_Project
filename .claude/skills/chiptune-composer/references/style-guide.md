# Style guide: orchestral-big-band adventure in chip form

The target sound comes from Dreamcast-era JRPG scores such as *Skies of Arcadia* (Yutaka Minobe and Tatsuyuki Maeda): a symphonic orchestra crossed with big-band brass, regional folk instruments for each place, and bright, clean synthesizer sequencing. This skill translates that into chip and FM voices. Aim for the feeling of open sky and adventure. Don't reproduce any of the actual themes.

## What makes it sound like this

**Brass carries the heroism.** Give the main melody to `trumpet`, with `horn` countermelodies underneath. Use leaps of a fourth, fifth or sixth, especially upward at phrase starts, since they read as fanfare. Accent the first note of a phrase with `!`.

**Big-band snap creates the energy.** Place short `trumpet_section` chords on off-beats (the "and" of 1, the "and" of 3) in the gaps between melody phrases. Melody and stabs should take turns, like call and response. Add `^` scoops and `v` falls in jazzier pieces, and don't overuse them.

**Strings give the scale.** A `strings` pad sits under the brass in close position, in octaves 3 and 4, with voices moving as little as possible between chords. For a swell of emotion, let the strings or a flute take the melody an octave up in the second section.

**Timpani marks the big moments.** Hit it on section starts and chord changes rather than constantly, and roll into important downbeats with fast repeated notes.

**The arpeggio is the chip signature.** A `arp` voice with `"arp": 0.25` plus a little `echo` stands in for orchestral figuration and adds the shimmer of older console music. Keep it below the melody and quiet.

**Bass moves.** It should drive, not just hold roots: eighth-note patterns for action, walking quarters for swing, root and fifth for folk. Land on the chord's bass note at every change.

## Harmony

Stay mostly diatonic and bright, with motion that keeps resolving forward.

- Lift into choruses using the IV or vi: in D, `G | A | F#m | Bm`.
- Use slash chords for stepping basslines: `D | A/C# | Bm | G`.
- Use ii-V before cadences: `Em7 A7 | D`.
- Delay endings with suspensions: `Asus4 A`.
- Borrow the bVII or bVI for a moment of grandeur: in D, `C` or `Bb` before returning.
- For a final-chorus lift, repeat the section with `"transpose": 2`, then add a short turnaround back to the original key's dominant so the loop lands correctly.

For battle music, use minor or dorian with blues notes and a riff in the low brass, then contrast it with a heroic major section.

## Recipes by game moment

| Moment | Tempo and meter | Lead | Rest of the band |
|---|---|---|---|
| Overworld or airship | 126-144, 4/4, straight | `trumpet`, then `flute` | horns, strings, arp, driving bass, timpani, rock-march drums |
| Port or trading town | 150-180 in 6/8, or 100-120 swung | `accordion`, `whistle`, `clarinet` | `guitar` boom-chuck, `upright`, tambourine, light strings |
| Regional island flavor | Varies | `whistle` or `oboe` with modal melody (dorian, mixolydian, phrygian) | `harp` or `guitar`, soft pad, hand percussion via `rim`, `shaker`, `tom_hi` |
| Normal battle | 160-190, 4/4, swing 0.6-0.64 | `sax` or `trumpet` | trombone riff, section stabs, walking `upright`, ride-led drums |
| Boss | 150-180, minor, straight | `trumpet_section` in unison | low brass ostinato, timpani, `strings_stab`, snare fills |
| Sad or quiet scene | 60-84 | `flute` or `oboe` | `strings`, `harp`, no drums |
| Victory jingle | 120-132, `loop: false`, 2-4 bars | `trumpet` triplet pickup | full band, ending on a held tonic with a crash |

## Melody habits that help

- Build each phrase from a short motif, then repeat it with one change. Listeners remember repetition.
- Use two-bar questions and two-bar answers, so eight bars feel like a sentence.
- Place the highest note about two-thirds of the way through the phrase.
- Mix long and short notes. A long note after quick ones is what feels like soaring.
- Leave space. Rests let the stabs answer and make chip voices sound less mechanical.

## Arranging for clarity

Chip voices are bright and mask each other more easily than acoustic instruments, so keep the texture open.

- Give each voice its own register, pan position and rhythm. Two voices that share all three will blur.
- Keep chord voicings below the melody, and avoid thick chords below about C3, where they turn to mud.
- Use around 6 to 9 voices. Bring in new ones at section changes instead of having everything play throughout.
- Vary the sections: change the lead instrument, swap hi-hat for ride, or drop out the drums for two bars.
- Give every section one drum fill leading into the next.

## Dramatic orchestral battle music

Use this for ship dogfights and bosses, where the music must stay tense through long turn-based fights without wearing the player out.

- **Tension engine:** run `strings_ostinato` in a gallop (eighth, two sixteenths) over `low_strings` accenting 3+3+2. This keeps the pulse urgent even while the harmony moves slowly.
- **Weight:** double the bass with `tuba` on long notes, and use `timpani` and `bdrum` on section starts. Save `gong` for arrivals so it keeps its impact.
- **Harmony:** heroic minor uses i-bVI-bIII-bVII (Dm Bb F C). Menace uses the Neapolitan (Cm Ab Db G) and a half-diminished ii before V.
- **Form:** creep with the theme low in the brass, state it in the trumpets, then give the fight a heart with a beautiful major section led by `strings_lead` over `harp` and `choir_pad`. Return with a key lift using a two-bar dominant, then turn back so the loop lands in the home key.
- **Length:** aim for a loop of about a minute. Players hear it for many turns, and the lyrical section is what stops it from tiring them.
- **Adaptive layer:** put high tremolo strings, low brass 3+3+2 stabs and snare in a second layer for danger or a boss's second phase.

## Adaptive layers

Keep the melody and harmony in `base`. Put intensity in named layers: low-brass ostinatos, marching snare, extra timpani. Because layers are heard both on and off, avoid putting anything in one that the harmony depends on.
