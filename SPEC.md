# netsmoke Project Specification

## Project Goal

We are building a modern clone of the "smokeping" network monitoring
application.  The goal is to be true to the original where possible,
while getting rid of some of the legacy technologies in the original
such as Perl, rrdtool, and CGI.

## Smokeping References for Comparison

* The smokeping source is available in @SmokePing/ . It can be consulted freely, as we are going to license this package under the same license as SmokePing and give credit to it. This is _not_ a cleanroom implementation.
* The smokeping website is <https://oss.oetiker.ch/smokeping/> and can be consulted freely.
* An example Smokeping demo install is available at <https://smokeping.oetiker.ch/>. Note that it has a feature that we are not implementing, which shows multiple source hosts in a single graph.  Only use that demo install for graphs that show a single latency line and grey smoke -- for example, the hosts under "O+P Internal" under "O+P Managed", but NOT the graphs under "Neplan".

## List of requirements

* netsmoke will graph network performance (ping latency and packet loss) between the host it is running on and an arbitrary list of target hosts, which can be organized into folders.
* The graphs must have the smoke visualization that was used in the original. That is an important feature of netsmoke, because the smoke graph was one of the best features of smokeping.
* The program should be easy to run locally in docker or a Kubernetes pod, but still scale up reasonably easy with a separate database.
* The main process should run constantly, unlike smokeping which had a separate data collector and CGI-based web app.
* Pinging sources should be done efficiently, not one-at-a-time.  Smokeping used "fping"; we can use "fping" or build the same functionality in native Python.
* Pinging must be ICMP-based.
* The targets and the folder hierarchy will be configured in a single config file. We can use yaml or toml for the configuration file, but not json, and it does not need to be backwards compatible with smokeping.
* Prefer client-side generated graphs, if we can make them look like smokeping. Fall back to server-side generation if you think that's better for appearance or architectural reasons. Client-side graph libraries may not work well with the amount of data we will store.
* Regardless of whether graph rendering is client- or server-side, the overall web app should be a React app.
* Don't implement authentication. Users will be expected to put authentication in front of this app.

## Smoke graphs

* There is sample code for generating smoke graphs in @smoke_poc_bars.py.
* There are notes from a previous Claude session in @GRAPHS.md which talks about how the graphs were implemented in Smokeping.
* A latency graph data point shows the following:
  * The height of the point is the median latency for that time.
  * The smoke shows the variance around the median, in the same way that Smokeping did.
  * The color of the point shows the amount of packet loss, from green through blue, purple, orange and red, just like in Smokeping.
* Graphs should be in png or svg format.
* Graphs should be created on demand, not pre-generated.

## Environment

Write the backend in python.  Use "uv" to create a virtualenv to work in and to manage project dependencies. Use whatever dependencies you feel are necessary, but well-established libraries are greatly preferred. Use a standard Python program layout.

Write the frontend in React. We will choose a CSS library as we plan the app (or use plain CSS if that's better).

While developing, prefer Docker for general app work, but run the backend directly on this Mac when you need trustworthy ICMP latency measurements. Colima distorts RTTs for this workload, so host-based backend development is the default for latency validation. If Docker is not running and you still want the container stack, start it with `colima start`.

For now, use sqlite as the datastore.  If we need to use sample data during development of the frontend and web backend, that's fine. Later we may add postgres timescaledb as an option.

Write unit tests as needed, for an appropriate level of test coverage.  This application will be maintained by an LLM, so being able to run tests for validation is important.  Use the Playwright CLI for browser testing.

This directory is a git repository. You can work in the current branch. Do not change branches. You should commit often, with understandable commit messages, and add a tag whenever we reach an important milestone in building the project, which I will use later to rebase history. You must NEVER do any git network operations such as "git push" or destructive options like "git reset".  If the repository state is messed up, stop and ask for help.
