"""The conversation layer: a LangGraph agent for a long, stateful phone call.

Where Temporal (see `temporal/`) orchestrates the case across days, this orchestrates the
reasoning inside a single call, turn by turn. The worked example is a prior-authorization
intake for a power wheelchair (K0856), which unlike Eleanor's K0001 needs prior auth and a
lot of clinical justification, so it is a genuinely long conversation.

The point of the build is context engineering: keep the window bounded on a long call
without losing the thread, by extracting the facts that matter into structured slots and
keeping a rolling summary instead of the raw transcript. It stays on the thesis: the agent
gathers information and hands it off, it never decides coverage or medical necessity.
"""
