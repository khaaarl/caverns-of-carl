import random


def choice(seq, weights=None, cum_weights=None):
    if cum_weights is not None:
        return random.choices(seq, cum_weights=cum_weights, k=1)[0]
    if weights is not None:
        return random.choices(seq, weights=weights, k=1)[0]
    return random.choice(seq)


class WeightTreeNode:
    def __init__(self, left_weight, value=None, left=None, right=None):
        self.left_weight = left_weight
        self.value = value
        self.left, self.right = left, right

    def find_and_remove(self, weight):
        if self.left is None:
            prev_left_weight = self.left_weight
            self.left_weight = 0.0
            return (prev_left_weight, self.value)
        if weight < self.left_weight:
            dweight, value = self.left.find_and_remove(weight)
            self.left_weight -= dweight
            return (dweight, value)
        else:
            dweight, value = self.right.find_and_remove(weight - self.left_weight)
            return (dweight, value)

    @staticmethod
    def build(seq, weights, ix0, ix1):
        if ix1 - ix0 == 1:
            if weights is None:
                weight = 1.0
            else:
                weight = weights[ix0]
            return (WeightTreeNode(left_weight=weight, value=seq[ix0]), weight)
        ixr = ix0 + ((ix1 - ix0) >> 1)
        left, left_weight = WeightTreeNode.build(seq, weights, ix0, ixr)
        right, right_weight = WeightTreeNode.build(seq, weights, ixr, ix1)
        return (
            WeightTreeNode(left_weight=left_weight, left=left, right=right),
            left_weight + right_weight,
        )


def samples(seq, k=1, weights=None):
    if k <= 0:
        return []
    elif k == 1:
        yield choice(seq, weights=weights)
        return
    elif k > len(seq):
        raise ValueError(
            f"Number of samples k requested ({k}) larger than population"
        )
    tree, total_weight = WeightTreeNode.build(seq, weights, 0, len(seq))
    for _ in range(k):
        weight = random.random() * total_weight
        dweight, value = tree.find_and_remove(weight)
        total_weight -= dweight
        yield value
