__author__ = 'matiascubero'

import numpy as np
from scipy.stats import sem

from sklearn import metrics
from Experimentos.Persistencia import *
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.datasets import fetch_20newsgroups
from sklearn.cross_validation import cross_val_score, KFold


def get_stop_words():
    result = set()
    for line in open('data/stopwords_en.txt', 'r').readlines():
        result.add(line.strip())
    return result

def evaluate_cross_validation(clf, X, y, K):
	# create a k-fold croos validation iterator of k=5 folds
	cv = KFold(len(y), K, shuffle=True, random_state=0)
	# by default the score used is the one returned by score method of the estimator (accuracy)
	scores = cross_val_score(clf, X, y, cv=cv)
	print scores
	print ("Mean score: {0:.3f} (+/-{1:.3f})").format(
		np.mean(scores), sem(scores))

def train_and_evaluate(clf, X_train, X_test, y_train, y_test):
    
    clf.fit(X_train, y_train)
    
    print "Accuracy on training set:"
    print clf.score(X_train, y_train)
    print "Accuracy on testing set:"
    print clf.score(X_test, y_test)
    
    y_pred = clf.predict(X_test)
    
    print "Classification Report:"
    print metrics.classification_report(y_test, y_pred)
    print "Confusion Matrix:"
    print metrics.confusion_matrix(y_test, y_pred)

def ejecutarMachineLearning():
	chistes = cargar_tweets()
	chistes2 = cargarChistes();
	
	news = fetch_20newsgroups(subset='all')
	SPLIT_PERC = 0.80

	split_size = int(len(chistes)*SPLIT_PERC)
	X_train = [chistes[i].texto for i in range(len(chistes))][:split_size]
	X_test = [chistes[i].texto for i in range(len(chistes))][split_size:]
	Y_train = [chistes[i].es_humor for i in range(len(chistes))][:split_size]
	Y_test = [chistes[i].es_humor for i in range(len(chistes))][split_size:]
	stop_words = get_stop_words()


	clf_4 = Pipeline([
		('vect', TfidfVectorizer(
					stop_words=stop_words,
					token_pattern=ur"\b[a-z0-9_\-\.]+[a-z][a-z0-9_\-\.]+\b",         
		)),
		('clf', MultinomialNB(alpha=0.01)),
	])

	clf_4.fit(X_train, Y_train)
	evaluate_cross_validation(clf_4, [chistes[i].texto for i in range(len(chistes))], [chistes[i].es_humor for i in range(len(chistes))], 5)

	train_and_evaluate(clf_4, X_train, X_test, Y_train, Y_test)




if __name__ == "__main__":
	ejecutarMachineLearning()