import math

def distance(ck1, ck2, weights=None):
    """
    Compute the distance between cocktails.

    """

    # Default to equal weights
    if weights is None: 
        w = [1,1]
    else:
        w = weights[:]

    ph = ph_distance(ck1, ck2)
    if ph is None:
        ph = 0
        w[0] = 0

    fp = fp_distance(ck1, ck2)
    if fp is None:
        fp = 0
        w[1] = 0

    # If all weights are 0, then technically it's undefined but we default to
    # max dissimilarity 
    if sum(w) == 0: return 1

    return ( (w[0]*ph) + (w[1]*fp) ) / sum(w)

def _braycurtis(fp1, fp2):
    """
    Compute the Bray-Curtis dissimilarity measure between fingerprint vectors.

    :returns: distance between 0 and 1
    """
    diff_sum = 0
    summ = 0
    for k in list(set(fp1.keys() + fp2.keys())):
        a = fp1.get(k, 0)
        b = fp2.get(k, 0)
        diff_sum += math.fabs(a - b)
        summ += math.fabs(a + b)

    if summ == 0: return 1

    return float(diff_sum)/float(summ)


def fp_distance(ck1, ck2):
    """
    Compute distance between fingerprint vectors

    :param cocktail cocktail1: First cocktail to compare
    :param cocktail cocktail2: Second cocktail to compare

    :returns: The distance score between 0 and 1, or None if either cocktail is missing a fingerprint
        
    """
    # either missing: undefined
    if ck1.fingerprint() is None or ck2.fingerprint() is None:
        return None


    return _braycurtis(ck1.fingerprint(), ck2.fingerprint())

def ph_distance(ck1, ck2):
    """
    Compute pH distance.

    :param cocktail cocktail1: First cocktail to compare
    :param cocktail cocktail2: Second cocktail to compare

    :returns: The distance score between 0 and 1 or None if cocktails are missing pH
        
    """
    # either missing: undefined
    if ck1.ph is None or ck2.ph is None: 
        return None

    return math.fabs(ck1.ph - ck2.ph) / 14
