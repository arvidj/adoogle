Adoogle
=======

A small script for searching in ``gnatinspect``-databases.

How to use:

 1. Run ``gnatinspect --db gnatinspect.db -P
     <Project.gpr>``. Gnatinspect can be found in
     [gnatcoll](https://docs.adacore.com/gnatcoll-docs/). This will
     generate a database of all symbols in your project.
 2. Run ``py adoogle.py gnatinspect.db "query"`` to query the
    database.

Supported queries
===============

* ``abs``: find any entity with the name ``abs``
* ``def : Blah``: find any entity with the name ``max`` of type ``Share``
* ``def : ->``: find any entity with the name ``max`` of which is a function
* ``(x,y,z) def``: find any entity with the name ``def`` and kinds x, y
or z (see ``entity_kinds.py``)
* ``(fun) def``: find any entity with the name ``def`` and which is
either a function or a procedure
* ``(pkt) def``: find any entity with the name ``def`` and which is either
a function or a procedure

To implement
============

 * ``max : Share -> Share``: find functions or procedure with the name ``max`` with two parameters of type ``Share``
