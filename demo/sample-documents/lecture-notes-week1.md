# CS 401 Lecture Notes — Week 1: Supervised Learning and the Bias-Variance Tradeoff

## What supervised learning means

A supervised learning problem has a dataset of input-output pairs
`(x_i, y_i)` and the goal is to learn a function `f` that predicts `y` for
inputs `x` it has never seen. The word "supervised" refers to the fact that
every training example comes with its correct answer attached. Classification
predicts a discrete label; regression predicts a continuous value.

The central assumption is that the training data and the test data are drawn
from the same distribution. When that assumption fails the model is being
asked to generalise to a world it has not seen, and no amount of extra training
data collected from the wrong distribution will fix it. This is called dataset
shift, and it is one of the most common reasons a deployed model fails in a way
the offline metrics never predicted.

## Linear regression

Linear regression predicts a continuous target as a weighted sum of the input
features:

```
y_hat = w_0 + w_1 * x_1 + w_2 * x_2 + ... + w_n * x_n
```

Fitting means choosing the weights `w` that minimise the sum of squared errors
between the predictions and the true values:

```
SSE(w) = sum over i of (y_hat_i - y_i)^2
```

The sum of squared errors is the *loss function* — the quantity the training
procedure tries to make small. Mean squared error, the SSE divided by the number
of examples, is the same thing rescaled and is used more often because it does
not grow with the size of the dataset.

The ordinary least squares solution has a closed form:

```
w = (X^T X)^-1 X^T y
```

This is exact and requires no iteration, which is why it is a useful baseline.
 It is also numerically unstable when `X^T X` is close to singular, and it
becomes intractable to invert directly once the number of features reaches the
thousands. Both problems are the reason gradient descent is the default in
practice rather than a historical curiosity.

## Gradient descent

Gradient descent replaces the closed form with iteration. At each step, move
the weights in the direction that most decreases the loss:

```
w := w - learning_rate * gradient(SSE(w), w)
```

The learning rate controls the size of each step. Too large and the iteration
overshoots and diverges, producing weights that grow without bound and a loss
that climbs instead of falling. Too small and convergence is so slow that the
model is still far from the optimum when training time runs out. Choosing it is
the single most important hyperparameter in the course, and the standard
practice is to try a range of values spaced by an order of magnitude and pick
the best on a validation set.

The gradient of the sum of squared errors with respect to the weights is
computable in closed form as `2 * X^T (X w - y)`, which makes each step cost
roughly the same as one matrix-vector product. This is what makes the method
scale: the work per step is linear in the number of examples.

Convergence is diagnosed by watching the loss curve. If the training loss
stops decreasing, the optimiser has converged. If the training loss keeps
falling while validation loss rises, the model is overfitting.

## The bias-variance tradeoff

The mean squared error of a model can be decomposed into three parts:

```
E[(y - y_hat)^2] = bias^2 + variance + irreducible noise
```

Bias is the error from systematically wrong assumptions — a linear model
predicting a curved relationship. Variance is the error from fitting the noise
in the particular training sample rather than the underlying pattern; a very
high-degree polynomial has almost no bias and enormous variance.

Model capacity trades one against the other. Simple models have high bias and
low variance. Complex models have the opposite. The optimal model is the one
that gets the balance right, and the practical symptom of getting it wrong is
clear in each direction: a model with too little capacity has a high training
*and* validation error, while a model with too much has a low training error
and a visibly higher validation error.

The practical remedy for high variance is more training data, and the
practical remedy for high bias is a more expressive model. Regularisation
attacking the variance term directly by penalising the magnitude of the weights.
