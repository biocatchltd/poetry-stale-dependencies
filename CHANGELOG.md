# poetry-stale-dependencies changelog
## 0.2.0
### Changed
* the `include_remote_prereleases` was renamed to `include_prereleases`
* the `project_path` argument is now an option
### Added
* README
* durations like `time-tostale` now accept the string `0` to indicate a zero duration
* `time_to_ripe`, to disable packages that were released in the past few days
* the users of a stale dependency, either other dependencies or the project itself, are now listed in the output
* users can now specify only some packages to be inspected via the command line
* users can now specify the time-to-ripe and time-to-stale via the command line

## 0.1.2
### Fixed
* fixed inspection method name

## 0.1.1
### Fixed
* fixed release workflow

## 0.1.0
* initial release