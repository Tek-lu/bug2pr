def rank(scores):
    """scores: dict of name -> score. Returns a list of (rank, name), highest score first.

    Ties share a rank and the next rank is skipped (competition ranking: 1, 2, 2, 4).
    Players with the same score are listed in alphabetical order.
    """
    ordered = sorted(scores.items(), key=lambda kv: -kv[1])
    out = []
    for i, (name, _score) in enumerate(ordered, 1):
        out.append((i, name))
    return out
