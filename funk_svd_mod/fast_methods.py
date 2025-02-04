import warnings

import numpy as np
from numba import njit
from numba.core.errors import NumbaDeprecationWarning, NumbaPendingDeprecationWarning

warnings.simplefilter('ignore', category=NumbaDeprecationWarning)
warnings.simplefilter('ignore', category=NumbaPendingDeprecationWarning)

__all__ = [
    '_compute_val_metrics',
    '_initialization',
    '_run_epoch',
    '_shuffle'
]


@njit
def _shuffle(X):
    np.random.shuffle(X)
    return X


@njit
def _initialization(n_users, n_items, n_factors):
    """Initializes biases and latent factor matrices.

    Parameters
    ----------
    n_users : int
        Number of unique users.
    n_items : int
        Number of unique items.
    n_factors : int
        Number of factors.

    Returns
    -------
    bu : numpy.array
        User biases vector.
    bi : numpy.array
        Item biases vector.
    pu : numpy.array
        User latent factors matrix.
    qi : numpy.array
        Item latent factors matrix.
    """
    bu = np.zeros(n_users)
    bi = np.zeros(n_items)

    pu = np.random.normal(0, .1, (n_users, n_factors))
    qi = np.random.normal(0, .1, (n_items, n_factors))

    return bu, bi, pu, qi


@njit
def _run_epoch(X, bu, bi, pu, qi, global_mean, n_factors, lr, reg, clusters_diff, is_women_dict, is_men_dict):
    """Runs an epoch, updating model weights (pu, qi, bu, bi).

    Parameters
    ----------
    X : numpy.array
        Training set.
    bu : numpy.array
        User biases vector.
    bi : numpy.array
        Item biases vector.
    pu : numpy.array
        User latent factors matrix.
    qi : numpy.array
        Item latent factors matrix.
    global_mean : float
        Ratings arithmetic mean.
    n_factors : int
        Number of latent factors.
    lr : float
        Learning rate.
    reg : float
        L2 regularization factor.

    Returns:
    --------
    bu : numpy.array
        User biases vector.
    bi : numpy.array
        Item biases vector.
    pu : numpy.array
        User latent factors matrix.
    qi : numpy.array
        Item latent factors matrix.
    """

    for i in range(X.shape[0]):
        user, item, rating = int(X[i, 0]), int(X[i, 1]), X[i, 2]

        # Predict current rating
        pred = global_mean + bu[user] + bi[item]

        for factor in range(n_factors):
            pred += pu[user, factor] * qi[item, factor]

        err = rating - pred

        # Update biases
        bu[user] += lr * (err - reg * bu[user])
        bi[item] += lr * (err - reg * bi[item])

        # Update latent factors

        old_qi = np.zeros(n_factors)
        new_qi = np.zeros(n_factors)

        for factor in range(n_factors):
            puf = pu[user, factor]
            qif = qi[item, factor]

            old_qi[factor] = qi[item, factor]
            new_qi[factor] = qi[item, factor] + lr * (err * puf - reg * qif)

            pu[user, factor] += lr * (err * qif - reg * puf)

        is_woman = item in is_women_dict
        is_men = item in is_men_dict
        cosine_sim = 0.0

        if is_woman or is_men:
            embedding_diff = new_qi - old_qi
            cosine_sim = np.dot(clusters_diff, embedding_diff) / \
                         (np.sqrt((clusters_diff ** 2).sum()) * np.sqrt((embedding_diff ** 2).sum()))

        # if product is for women, then similarity should be > 0
        # if product is for men, then similarity should be < 0

        if cosine_sim < 0 and is_woman:
            qi[item] = old_qi - cosine_sim * (new_qi - old_qi)
        elif cosine_sim > 0 and is_men:
            qi[item] = old_qi + cosine_sim * (new_qi - old_qi)
        else:
            qi[item] = new_qi

    return bu, bi, pu, qi


@njit
def _compute_val_metrics(X_val, bu, bi, pu, qi, global_mean, n_factors):
    """Computes validation metrics (loss, rmse, and mae).

    Parameters
    ----------
    X_val : numpy.array
        Validation set.
    bu : numpy.array
        User biases vector.
    bi : numpy.array
        Item biases vector.
    pu : numpy.array
        User latent factors matrix.
    qi : numpy.array
        Item latent factors matrix.
    global_mean : float
        Ratings arithmetic mean.
    n_factors : int
        Number of latent factors.

    Returns
    -------
    loss, rmse, mae : tuple of floats
        Validation loss, rmse and mae.
    """
    residuals = []

    for i in range(X_val.shape[0]):
        user, item, rating = int(X_val[i, 0]), int(X_val[i, 1]), X_val[i, 2]
        pred = global_mean

        if user > -1:
            pred += bu[user]

        if item > -1:
            pred += bi[item]

        if (user > -1) and (item > -1):
            for factor in range(n_factors):
                pred += pu[user, factor] * qi[item, factor]

        residuals.append(rating - pred)

    residuals = np.array(residuals)
    loss = np.square(residuals).mean()
    rmse = np.sqrt(loss)
    mae = np.absolute(residuals).mean()

    return loss, rmse, mae
