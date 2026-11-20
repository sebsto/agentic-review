Rules for every finder. They come from review comments that maintainers
accepted and rejected on past pull requests.

1. Report defects only. Never write praise, "looks good", "no change needed",
   "confirming, not a defect", or a question for the author. If you would write
   one of those, leave the finding out.
2. State the premise. Your explanation must name the language, compiler or
   framework rule your claim depends on. Past false claims, all wrong:
   - "`[K: V?]` assignment of nil removes the key". It does not when the value
     type is optional; the setter takes `V??`.
   - "`AnyHashable as? String` does not unwrap". It does.
   - "An enum with no payload is not `Equatable`". It is, implicitly.
   - "A `public` member in an internal type is rejected". It is legal.
   - "A closure inside a `@MainActor` context may run off the main actor". It
     is inferred `@MainActor` when it is not `Sendable`.
   - "An unstructured `Task {}` from a `@MainActor` context resumes off the
     main actor". It inherits the actor.
   - "`NO_COLOR=` (set but empty) reads as unset". `ProcessInfo` returns `""`.
   - "`localizedDescription` is useless for a POSIX error". It has the reason.
   If you are not sure of a Swift rule, leave the finding out.
3. Respect the build. If the CI checks show the commit built and tests passed,
   do not claim it fails to compile or that a test fails. If CI is red, the
   failing job is a finding.
4. Respect intent. Read the PR description, the design or spec docs in the
   repo and REVIEW.md. Do not report behaviour the author chose on purpose
   and documented there. Do not repeat a point in "Earlier review discussion"
   that the author already answered with a reason.
5. Skip unlikely cases: accounts with more than a page of results, inputs the
   caller controls, values only the stack sets, "if this ever moves". Report a
   case only when you can show a normal path that reaches it.
6. One finding per root cause. Do not report the same cause at several lines.
7. A finding that points at the line "already there" must quote the old line
   from the diff and say what in the new code makes it wrong.
