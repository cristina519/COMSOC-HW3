import time

def parse_ranking(pref_str):
    """
    Parse a preference string (with possible tie groups) into a list of ranked groups.
    """
    ranking = []
    i = 0
    n = len(pref_str)

    while i < n:
        if pref_str[i].isspace() or pref_str[i] == ",":
            i += 1
            continue

        # Data has blocks like: { a, b, c }
        if pref_str[i] == "{":
            i += 1
            group = []
            num = ""

            while i < n and pref_str[i] != "}":
                if pref_str[i].isdigit():
                    num += pref_str[i]
                elif pref_str[i] in ", ":
                    if num:
                        group.append(int(num))
                        num = ""
                else:
                    pass
                i += 1

            if num:
                group.append(int(num))
            ranking.append(group)
            i += 1 

        else:
            num = ""
            while i < n and pref_str[i].isdigit():
                num += pref_str[i]
                i += 1
            if num:
                ranking.append([int(num)])

    return ranking

def read_dataset(path):
    """
    Read the dataset file and extract candidates, their names, and the list of ballots.
    """
    candidates = set()
    cand_names = {}
    ballots = []

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            if line.startswith("#"):
                if "ALTERNATIVE NAME" in line:
                    left, name = line.split(":", 1)
                    cid = int(left.split()[-1])
                    cand_names[cid] = name.strip()
                    candidates.add(cid)
                continue

            if ":" in line:
                count_str, pref_str = line.split(":", 1)
                weight = int(count_str.strip())
                ranking = parse_ranking(pref_str.strip())

                for group in ranking:
                    for c in group:
                        candidates.add(c)

                ballots.append((weight, ranking))

    return sorted(candidates), cand_names, ballots


def plurality_scores(remaining, ballots):
    """
    Compute plurality scores for the current round: 
    each ballot gives its weight to the highest-ranked
    remaining candidates, splitting if tied
    """
    scores = {c: 0.0 for c in remaining}

    for weight, ranking in ballots:
        for group in ranking:
            group_rem = [c for c in group if c in remaining]
            if group_rem:
                share = weight / len(group_rem)
                for c in group_rem:
                    scores[c] += share
                break  # stop at first non-empty rank
        # If no remaining candidates appear, ballot is exhausted and ignored

    return scores


def stv(candidates, ballots):
    """
    Run the STV elimination rule: 
    iteratively remove all candidates with
    the lowest plurality score until none remain.
    Return the final winners and elimination order
    """
    remaining = set(candidates)
    elimination_order = []
    last_losers = None

    while remaining:
        scores = plurality_scores(remaining, ballots)
        min_score = min(scores[c] for c in remaining)

        # All candidates with minimal plurality score are removed 
        losers = [c for c in remaining if abs(scores[c] - min_score) < 1e-9]

        for c in losers:
            remaining.remove(c)
            elimination_order.append(c)

        last_losers = losers

    winners = last_losers
    return winners, elimination_order



# Manipulation functions

def candidate_position(ranking, cand):
    """
    Return rank index of candidate in ranking
    """
    for idx, group in enumerate(ranking):
        if cand in group:
            return idx
    return None


def prefers_over(ranking, cand1, cand2):
    """
    Checks whether candidate 1 is strictly preferred over candidate 2 in this ranking
    """
    pos1 = candidate_position(ranking, cand1)
    pos2 = candidate_position(ranking, cand2)

    if pos1 is None and pos2 is None:
        return False
    if pos1 is None:
        return False            # doesn't rank cand1 at all
    if pos2 is None:
        return True             # ranks cand1 but not cand2
    return pos1 < pos2          # smaller index = more preferred


def build_strategic_ballot_from_ranking(ranking, target, winner, all_candidates):
    """
    Builds a strategic ballot for a voter:
    target is moved to top,
    winner is moved to bottom,
    all other candidates keep their original order
    """
    flat = []
    for group in ranking:
        for c in group:
            if c not in flat:
                flat.append(c)

    for c in all_candidates:
        if c not in flat:
            flat.append(c)

    if target in flat:
        flat.remove(target)
    flat.insert(0, target)

    if winner in flat:
        flat.remove(winner)
    flat.append(winner)

    return [[c] for c in flat]


def apply_manipulation(ballots, type_index, k, strategic_ballot):
    """
    Return a new ballots list where k voters from ballot-type 
    `type_index` are replaced by k strategic ballots
    """
    new_ballots = []

    for idx, (w, r) in enumerate(ballots):
        if idx == type_index:
            if w - k > 0:
                new_ballots.append((w - k, r))
        else:
            new_ballots.append((w, r))

    # add k copies of strategic ballot as a separate type
    new_ballots.append((k, strategic_ballot))
    return new_ballots


def find_smallest_manipulating_coalition(candidates, ballots):
    """
    Search for the smallest coalition of voters that,
    by all submitting the same ballot, can change the
    STV winner to someone they all prefer.

    The coalition must come from a single ballot type.
    """
    orig_winners, _ = stv(candidates, ballots)
    if len(orig_winners) != 1:
        print("Original election has multiple winners; manipulation search assumes a single winner.")
        return None
    orig_winner = orig_winners[0]

    best_k = None
    best_target = None
    best_type_index = None
    best_true_ranking = None
    best_strategic_ballot = None
    best_new_elim_order = None

    for target in candidates:
        if target == orig_winner:
            continue

        for type_index, (weight, ranking) in enumerate(ballots):
            if not prefers_over(ranking, target, orig_winner):
                continue

            strategic_ballot = build_strategic_ballot_from_ranking(
                ranking, target, orig_winner, candidates
            )

            for k in range(1, weight + 1):
                manipulated_ballots = apply_manipulation(
                    ballots, type_index, k, strategic_ballot
                )

                new_winners, new_elim_order = stv(
                    candidates, manipulated_ballots
                )

                if len(new_winners) == 1 and new_winners[0] == target:
                    if best_k is None or k < best_k:
                        best_k = k
                        best_target = target
                        best_type_index = type_index
                        best_true_ranking = ranking
                        best_strategic_ballot = strategic_ballot
                        best_new_elim_order = new_elim_order
                    break

    if best_k is None:
        return None

    return {
        "orig_winner": orig_winner,
        "coalition_size": best_k,
        "target": best_target,
        "type_index": best_type_index,
        "true_ranking": best_true_ranking,
        "strategic_ballot": best_strategic_ballot,
        "new_elim_order": best_new_elim_order,
    }



if __name__ == "__main__":
    path = "dataset.txt"
    candidates, cand_names, ballots = read_dataset(path)

    #  Original election
    winners, elim_order = stv(candidates, ballots)

    print("Original elimination order (first out -> last out):")
    print(elim_order)
    print("Original winner(s) by ID:", winners)
    print("Original winner(s) by name:")
    for w in winners:
        print(f"{w}: {cand_names.get(w, 'UNKNOWN')}")
    print()

    # Timing the manipulation search
    start = time.time()
    result = find_smallest_manipulating_coalition(candidates, ballots)
    end = time.time()
    runtime = end - start

    print(f"\nManipulation search runtime: {runtime:.4f} seconds\n")

    # Manipulation search results
    if result is None:
        print("No manipulating coalition found under the search model (single ballot type, common ballot).")
    else:
        print("Election is manipulable under the search model.\n")
        print(f"True winner (before manipulation): {result['orig_winner']} "
              f"({cand_names.get(result['orig_winner'], 'UNKNOWN')})")
        print(f"Smallest coalition size: {result['coalition_size']} voters")
        print(f"Coalition comes from ballot type index: {result['type_index']}")
        print("True ranking of that type:", result["true_ranking"])
        print("Strategic ballot they all submit:", result["strategic_ballot"])
        print(f"New winner after manipulation: {result['target']} "
              f"({cand_names.get(result['target'], 'UNKNOWN')})")
        print("New elimination order under manipulation:")
        print(result["new_elim_order"])
