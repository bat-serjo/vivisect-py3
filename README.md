###This is a spin-off of the official vivisect project.  
The idea is to port the project to python3 and improve it on the way.  
In order to achieve this the commit rules will be very liberal.  
Think of this as a playground, a place to test any ideas.

Here are the rules of the game:
- Anyone can get commit access to this repo. 
In order to do so one must supply one meaningful patch or bug fix. 
Then contact any of the admins and ask for such access. Original contributors to the project
are more than welcome and only have to ask for the access nothing more.
- The master branch does not have to be rock solid, as a matter of fact it will 
probably often be broken. The idea is all contributors to work together on it.
When a working state (or some kind of milestone) gets reached a tag will be made.
Consider the tags to be stable and usable.
- How to commit. If you have a small patch or even a big one that merges fine and 
does not break anything just push it on the master. If you want to do something really wild
that will break things for a long time you have two options: 
    - Work in a branch (your branch your rules) there you can team up with other contributors etc.
     Once you get to a working point you can suggest a merge in master.
    - Discuss what you want to do with everybody and if it is agreed to do it we will start doing it
    in the master branch and everybody should work in that direction.




# Vivisect / Vdb / Vtrace

Now all as one project! ( made sense once vivisect went public )
For more in-depth docs on various topics, see the wiki at
[http://visi.kenshoto.com/](http://visi.kenshoto.com/)

## Vdb

As in previous vdb releases, the command ```python vdbbin``` from the
checkout directory will drop you into a debugger prompt on supported
platforms. ( Windows / Linux / FreeBSD / OSX... kinda? )

Commands in vdb grow/refine quickly, so use in-line help such as:

> vdb> help

or...

> vdb> help writemem

to show available commands and options.  Additionally, for basic vdb
use, the wiki at [http://visi.kenshoto.com/](http://visi.kenshoto.com/)

## Vivisect

Fairly un-documented static analysis / emulation / symbolik analysis
framework for PE/Elf/Mach-O/Blob binary formats on various architectures.
To start with, you probably want to run a "bulk analysis" pass on a binary
using:

> python vivbin -B <binaryfile>

which will leave you with <binaryfile>.viv

Then run:

> python vivbin <binaryfile>.viv

to open the GUI and begin reverse engineering.  As with most vtoys, the ui
relies fairly heavily on right-click context menus and various memory
views.

For the binary ninjas, all APIs used during automatic analysis ( and several
that aren't ) are directly accessible for use writing your own custom
research tools...  The interface should be nearly the same when dealing with
a real process ( via vdb/vtrace ) and dealing with an emulator / viv workspace.

## Build Status

[![Build Status](https://travis-ci.org/vivisect/vivisect.svg?branch=master)](https://travis-ci.org/vivisect/vivisect)
