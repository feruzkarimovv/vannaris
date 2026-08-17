# Z Fellows interview — read-aloud practice script

No figures anywhere, on purpose. Say it in plain sentences first; the exact numbers are in
`zfellows-interview-brief.md` if they ask, and they will only ask about two or three of them.
Practice by reading a section out loud, then closing this and saying it again in your own words.

---

## What it is

I build Vannaris. It's an independent benchmark of the web-search APIs that AI agents run on.

Every AI agent that touches the web calls a search API. Developers pick one based on marketing,
because there's nothing else to pick on. Every benchmark in the category is published by one of the
vendors being compared, and every one of them wins its own benchmark.

So I built the neutral one. Same questions, every vendor, every answer graded by language models
from rival labs, published free with the raw data. It's live, and anyone can check my work.

---

## What's changed since I applied

Two things, and both of them happened in the last two days.

The first one happened this morning. The benchmark ran itself for the first time. Until today,
every week that got published was started by me pressing a button. The schedule had been armed for
weeks and it had failed three times — once on a billing check, once on rate limits, once it had to
be run by hand. So I never described it as weekly, anywhere, because it wasn't. This morning it
woke up on its own, ran clean, and published the week without me. That's the week the clock
actually starts on.

It was also the cleanest run I've had. Almost every single answer came back with a complete set of
grades, which is better than any previous week, because of fixes I shipped last week that save the
vendor responses before the grading step instead of after. Before that change, a failure halfway
through grading threw away the entire week. Now the week survives and can be re-graded.

The second thing happened yesterday. My judges are language models, and until yesterday nobody had
ever checked whether they agree with a human. That caveat was sitting on three pages of my own
site. Now it's measured, and it's published.

---

## The human check, and why it matters

This is the question every AI evaluation company has and almost none of them answer. If a model is
grading the work, who says the model is right?

So I ran a blind study on myself. Pairs of answers, side by side. Vendor names hidden. The models'
own scores hidden. Which one the models preferred, hidden. Left and right randomised on every pair.
And I planted two traps in it.

The first trap was the same answer shown on both sides at different points, to catch me if I was
just picking a side out of habit. I never did.

The second trap was the same pair shown to me twice, far apart, to catch me if I was answering at
random. I gave the same answer both times, every time.

And on the pairs where the models had a clear opinion, I agreed with them most of the time. The
exact rate and the confidence interval are on the methodology page. I published it before I knew
whether it would make me look good.

The honest limit is that it's one person, and that person is me. That's the next thing to fix. But
the blinding is real and the two traps are what stop a single labeller from being meaningless.

---

## The finding, and how it killed my own product

Here's the part I'm actually proud of.

I didn't build the benchmark for its own sake. I built it to support a product — a router that
looks at each query and sends it to whichever search API is best for that kind of question. The
benchmark was going to be the thing that told the router where to send things.

Then I ran it. And the data said that even with perfect foresight — even if you always sent every
question to exactly the right vendor — you'd beat just always calling the best single vendor by a
rounding error. Not a small gain. Essentially nothing. And that held across every week I've
published since.

So there was nothing to route on. My whole product had no reason to exist.

At that point I had two options. I could have quietly adjusted the benchmark until it agreed with
me — reweighted the categories, swapped in a friendlier judge, reported the metric that made
routing look valuable. Nobody would have caught it, because I'm the only one with the data.

Or I could accept the result.

I killed the product and kept the instrument. That's the whole story of this company so far.

---

## What the benchmark actually shows

The cheapest API in the set costs a fraction of what the most expensive one costs, and on most
categories of question it's very nearly as good. It only really falls behind on the hard ones —
multi-step questions and obscure ones.

Most individual questions have no clear winner at all. The top two vendors are now statistically
tied. That's not a boring result, that's the finding — these things are sold as meaningfully
different and most of the time they aren't.

And the leaders shift. It used to be one vendor winning every category. Now it's split between two.
That only shows up because the thing runs repeatedly instead of once.

---

## Why anyone should trust the numbers

I grade with models from three rival labs, not one. One model's quirks shouldn't become the
results.

Those judges disagree with each other, sometimes badly, and I publish the disagreement rate — per
run and broken out by category. They agree almost perfectly on simple factual questions and they
fight over multi-step ones. Any benchmark reporting a single clean number is hiding this.

I re-run the entire ranking with each lab's judge removed, one at a time, to see if the answer
depends on who's grading. Mostly it doesn't. But under one lab's judge alone, the top two vendors
swap places — and that's published too. It's the single finding that most undermines my own
headline, and it's on the site.

I check whether longer answers just score higher for being longer. For most vendors the effect is
zero or slightly negative. For one vendor this week it went positive, which is a real caveat, and
I'd rather say it than have someone find it.

And there's a withheld set of questions whose fingerprint was committed publicly before it ever
ran, so nobody — including me — can tune against them.

---

## How it's built

The repository is public. The raw data is public, exported every week.

There's a single command that runs every check before anything publishes, and a run that's
methodologically broken fails rather than going out.

Not one figure on the site is typed in by hand. Every number, including the ones inside sentences,
is filled in from the generated data when the page loads, and the build fails if any of them
doesn't resolve.

And the sentences about how often it runs are derived from who triggered each run, not written by
me. That's why nothing needed editing this morning when the schedule finally started. The site just
knew.

The whole thing runs for about the price of a couple of lunches a month. So the record accrues
whether or not anyone ever funds it.

---

## What isn't true yet

I'd rather say these than have them found.

The withheld question set has never actually produced data. It's registered, the fingerprint is
committed, it's described on the site — and a configuration secret isn't set, so it's been quietly
sitting out every run including this morning's. Its rotation promise runs out at the start of next
month.

Nobody has been asked to pay for anything. Not one conversation. Every business model I've had so
far, I reasoned my way to alone instead of hearing it from someone who'd buy.

There's been no public launch. The thread where developers described this exact problem in their
own words — the most pre-qualified group of potential users I know of — I still haven't messaged.

And the instrument is running out of room. Almost all the vendors are scoring near the top of my
scale, and most questions come back tied. If I don't make the questions harder, the table stops
changing, and a benchmark whose answer never changes has no reason to be visited twice.

---

## What's next

Make the questions harder. That's the one change that fixes the saturation, restores the gaps
between vendors, and is the only thing that could revive the routing idea I killed.

Get the withheld set actually running before its deadline.

Launch publicly, and message the developers who already described this problem.

And ask someone to pay for a private evaluation — the same harness run on their own real queries,
which is the one thing nobody can copy out of my free data. One sale or one clear rejection turns
three guesses into one fact.

---

## If they ask what you need

I've built the instrument and never once asked anyone to pay for it. My instinct when I don't know
something is to go build more, and that's the habit I need broken. What I want is to be in a room
with people who've already taken something from working to used.

---

## Three lines to have ready

**What did you build?** An independent benchmark of the search APIs AI agents run on. Every vendor
gets the same questions, every answer is graded by models from rival labs, and all of it is
published free with the raw data. Every vendor in the category publishes a benchmark and every one
wins its own. I built the neutral one.

**What did you learn?** That the product I was building shouldn't exist. I wanted a router that
picks the best vendor per question. My own data said perfect routing beats just always using the
best vendor by a rounding error. So I changed the product and kept the instrument.

**What's hard right now?** I've built the thing and never asked anyone to pay for it. I can build
alone. I can't meet people alone.
