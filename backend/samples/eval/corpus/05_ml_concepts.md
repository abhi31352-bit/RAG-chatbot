# CS 401 Machine Learning — Lecture Notes, Weeks 1–7

Course content notes for the first half of term. These notes accompany the
lectures and are not a substitute for them; anything marked "exam" has been
covered in a past examination.


## Week 1 — Supervised learning and linear models

A supervised learning problem has a dataset of labelled examples and a
function that maps inputs to labels. Linear regression predicts a continuous
target as a weighted sum of features. The weights are chosen by minimising the
sum of squared errors between prediction and truth.

The normal equation gives the optimal weights in closed form, inverting the
matrix of feature cross-products. It is worth knowing because it shows the
problem has an exact solution, but it should not be used in practice: inverting
the matrix is numerically unstable and costs cubic time in the number of
features. Gradient descent is used instead. **(exam)**

Classification is the same problem with a discrete target. Logistic regression
applies a sigmoid to the linear score, giving a probability, and is trained by
minimising cross-entropy loss. Cross-entropy penalises confident wrong
answers far more than uncertain ones, which is why it replaced squared error
for classification. **(exam)**


## Week 2 — Regularisation and overfitting

Overfitting is the central failure mode of supervised learning. A model with
enough capacity can drive training error to zero while performing worse than a
trivial model on unseen data. The gap between training and validation error is
the diagnostic.

Regularisation constrains the model to reduce this gap. L2 regularisation adds
the sum of squared weights to the loss, which shrinks weights smoothly toward
zero. L1 regularisation adds the sum of absolute weights, which drives some
weights to exactly zero and therefore performs feature selection.

The difference between L1 and L2 is a frequent examination question. L1
produces sparse solutions because the penalty is non-differentiable at zero;
L2 produces dense small weights. In a regression problem with two correlated
features, L1 will typically set one of them to zero and keep the other, while
L2 keeps both at roughly half the size. **(exam)**

Cross-validation is how the regularisation strength is chosen. You should
never tune on the test set. A common and serious mistake is to select the
model using the test set, which makes the reported error an optimistically
biased estimate of nothing in particular.


## Week 3 — Gradient descent

Gradient descent updates parameters by moving opposite the gradient of the
loss. The learning rate controls the step size. Too small and training is slow;
too large and the loss diverges or oscillates and never converges.

SGD uses one example per step. Mini-batch gradient descent uses a small batch,
typically 32 to 256 examples, and is the usual default because it is both fast
and stable. Full batch gradient descent is stable but slow for large datasets.

Momentum accumulates an exponentially weighted average of past gradients, which
helps escape the ravines that appear in the loss surface of overparameterised
models. Adam adds adaptive per-parameter step sizes on top of momentum and is
the default optimiser in most deep learning frameworks. **(exam)**


## Week 4 — Evaluation and classification metrics

Accuracy is misleading whenever classes are imbalanced. A model that always
predicts the majority class scores high accuracy and is useless.

Precision is the fraction of predicted positives that are actually positive.
Recall is the fraction of actual positives that were found. They trade off
against each other: lowering the decision threshold raises recall and lowers
precision.

The F1 score is the harmonic mean of precision and recall, and is the right
single number when the two matter equally. The area under the precision-recall
curve is the better summary when the threshold is to be tuned. For heavily
imbalanced problems, the precision-recall curve is more informative than the
receiver operating characteristic curve, which can look deceptively good.


## Week 5 — Decision trees and ensembles

A decision tree splits on features recursively to reduce impurity. Trees fit
the training data perfectly, so a single tree almost always overfits, and
growing it to zero error is not the goal.

Random forests fix this by training many trees on bootstrap samples of the
data and random subsets of the features, then averaging their predictions.
Bagging reduces variance without introducing the bias of a single weak learner.

Boosting differs from bagging in that trees are added sequentially, each one
fitted to the residual errors of the trees already present. Gradient boosted
trees fit the negative gradient of the loss with a shallow tree, which is why
they almost always outperform random forests on tabular data. **(exam)**

The bias-variance tradeoff is the lens for all of this. Bagging reduces
variance. Boosting reduces bias. The ensembling literature is largely a study
of which one to buy.


## Week 6 — Unsupervised learning and clustering

K-means partitions data into k clusters by alternating assignment and centroid
update. It assumes clusters are roughly spherical, similarly sized, and
separable, and it is sensitive to initialisation; the standard practice is to
run it many times with different initialisations and keep the best inertia.

K-means is not appropriate when clusters have different densities or when the
number of clusters is not known. DBSCAN groups points by density and can find
arbitrarily shaped clusters, but needs both an epsilon neighbourhood radius and
a minimum points threshold, and it struggles with clusters of differing density.

Choosing k is usually done with the elbow method, plotting inertia against k
and looking for the bend, or with the silhouette score, which compares
within-cluster distance to nearest-other-cluster distance.


## Week 7 — Evaluation of unsupervised methods

There are no labels, so cluster quality is assessed against the algorithm's own
objective or against stability. Inertia always decreases as k increases, so it
cannot be used to choose k directly, only to find the elbow.

The silhouette score ranges from minus one to one. Above about 0.5 indicates
strong structure, near zero indicates weak structure, and negative values mean
points have been assigned to clusters they are further from than to other
clusters, which is a sign the clustering is actively wrong.

Adjusted Rand index compares a clustering to a ground truth labelling and is
adjusted for chance. It is the appropriate measure in the semi-supervised case
where labels exist for a subset of the data. **(exam)**
