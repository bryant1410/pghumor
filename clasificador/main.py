#!/usr/bin/env python2
# coding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals

import argparse
import os
import random
import sys

from flask import Flask, request
import flask
from flask_cors import cross_origin
from sklearn import linear_model, naive_bayes, neighbors, preprocessing, svm, tree
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_selection import RFECV
from sklearn.grid_search import GridSearchCV
from sklearn.pipeline import FeatureUnion, Pipeline


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from clasificador.features.features import Features
from clasificador.herramientas.define import parameters_svm, parameters_dt, \
    parameters_gnb, parameters_mnb, parameters_knn
from clasificador.herramientas.mayoria import Mayoria
from clasificador.herramientas.persistencia import cargar_tweets, guardar_features
from clasificador.herramientas.tweetstofeatures import TweetsToFeatures
from clasificador.herramientas.tweettotext import TweetToText
from clasificador.herramientas.utilclasificacion import cross_validation_y_reportar, \
    get_clases, get_features, matriz_de_confusion_y_reportar, train_test_split_pro, \
    mostrar_medidas_ponderadas
from clasificador.herramientas.utilanalisis import chi2_feature_selection, \
    f_score_feature_selection, imprimir_importancias, tree_based_feature_selection, tweets_parecidos_con_distinto_humor, \
    mismas_features_distinto_humor
from clasificador.herramientas.utils import entropia, filtrar_segun_votacion, get_stop_words
from clasificador.realidad.tweet import Tweet

# Ver esto: http://ceur-ws.org/Vol-1086/paper12.pdf
# Ver esto: https://stackoverflow.com/questions/8764066/preprocessing-400-million-tweets-in-python-faster
# Ver esto: https://www.google.com.uy/search?q=preprocess+tweet+like+normal+text

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Clasifica humor de los tweets almacenados en la base de datos.')
    parser.add_argument('-a', '--calcular-features-faltantes', action='store_true', default=False,
                        help="calcula el valor de todas las features para los tweets a los que les falta calcularla")
    parser.add_argument('-c', '--clasificador', type=unicode, default="SVM",
                        choices=["DT", "GNB", "kNN", "LB1", "LB2", "LinearSVM", "MNB", "SGD", "SVM"],
                        help="establece qué tipo de clasificador es usado, que por defecto es SVM")
    parser.add_argument('-x', '--cross-validation', action='store_true', default=False,
                        help="para hacer validación cruzada")
    parser.add_argument('-D', '--dudosos', action='store_true', default=False,
                        help="clasifica los tweets dudosos")
    parser.add_argument('-e', '--evaluar', action='store_true', default=False,
                        help="para evaluar con el corpus de evaluación")
    parser.add_argument('-b', '--explicar-features', action='store_true', default=False,
                        help="muestra las features disponibles y termina el programa")
    parser.add_argument('-j', '--feature-aleatoria', action='store_true', default=False,
                        help="agrega una feature con un valor binario aleatorio")
    parser.add_argument('-k', '--feature-clase', action='store_true', default=False,
                        help="agrega una feature cuyo valor es igual a la clase objetivo")
    parser.add_argument('-g', '--grid-search', action='store_true', default=False,
                        help="realiza el algoritmo grid search para el ajuste de parámetros")
    parser.add_argument('-G', '--grupo-de-calificacion', type=int, choices=[1, 2, 3, 4, 5],
                        help="establece a qué grupo de promedio de humor restringir el corpus")
    parser.add_argument('-i', '--importancias-features', action='store_true', default=False,
                        help="reporta la importancia de cada feature")
    parser.add_argument('-z', '--incluir-chistes-sexuales', action='store_true', default=False,
                        help="incluye en el entrenamiento y en la evaluación los chistes censurados")
    parser.add_argument('-l', '--limite', type=int,
                        help="establece una cantidad límite de tweets aleatorios a procesar")
    parser.add_argument('-m', '--mismas-features-distinto-humor', action='store_true', default=False,
                        help="imprime los pares de tweets que tienen los mismos valores de features"
                             + " pero uno positivo y el otro negativo")
    parser.add_argument('-q', '--medidas-ponderadas', action='store_true', default=False,
                        help="imprime las medidas precisión, recall y f1 ponderadas"
                             + " según el porcentaje de votos positivos")
    parser.add_argument('-p', '--parametros-clasificador', action='store_true', default=False,
                        help="lista los parámetros disponibles para el clasificador elegido")
    parser.add_argument('-n', '--ponderar-segun-votos', action='store_true', default=False,
                        help="en la clasificación pondera los tweets según la concordancia en la votación."
                             + " Funciona sólo para DT y SVM")
    parser.add_argument('-s', '--recalcular-features', action='store_true', default=False,
                        help="recalcula el valor de todas las features")
    parser.add_argument('-f', '--recalcular-feature', type=unicode, metavar="NOMBRE_FEATURE",
                        help="recalcula el valor de una feature dada")
    parser.add_argument('-C', '--reportar-informacion-corpus', action='store_true', default=False,
                        help="reporta cómo está conformado el corpus respecto a positivos y negativos,"
                             + " y respecto a entrenamiento y evaluación")
    parser.add_argument('-d', '--rfe', action='store_true', default=False,
                        help="habilita el uso de Recursive Feature Elimination antes de clasificar")
    parser.add_argument('-r', '--servidor', action='store_true', default=False,
                        help="levanta el servidor para responder a clasificaciones")
    parser.add_argument('-E', '--sin-escalar', action='store_true', default=False,
                        help="establece que no deben escalarse las características")
    parser.add_argument('-S', '--solo-subcorpus-humor', action='store_true', default=False,
                        help="entrena y evalúa sólo con los positivos")
    parser.add_argument('-N', '--subconjunto-no-humor', type=str, default=None,
                        choices=["Noticias", "Curiosidades", "Reflexiones"],
                        help="selecciona solamente el subconjunto pasado como parámetro de los negativos")
    parser.add_argument('-t', '--threads', type=int,
                        help="establece la cantidad de threads a usar al recalcular las features", default=1)
    parser.add_argument('-o', '--tweets-parecidos-distinto-humor', action='store_true', default=False,
                        help="busca y quita los pares de tweets que son parecidos pero uno positivo y el otro negativo")
    args = parser.parse_args()

    if args.explicar_features:
        features_obj = Features(args.threads)
        for feature in sorted(list(features_obj.features.values()), key=lambda x: x.nombre):
            print(feature.nombre + ":")
            print(feature.descripcion)
    else:
        corpus = cargar_tweets(args.limite, args.incluir_chistes_sexuales)

        if args.solo_subcorpus_humor:
            corpus = [tweet for tweet in corpus if tweet.es_chiste]

        if not args.clasificador.startswith("LB"):
            for tweet in corpus:
                tweet.preprocesar()

        if args.recalcular_features:
            features_obj = Features(args.threads)
            features_obj.calcular_features(corpus)
            guardar_features(corpus)
        elif args.recalcular_feature:
            features_obj = Features(args.threads)
            features_obj.calcular_feature(corpus, args.recalcular_feature.decode('utf-8'))
            guardar_features(corpus, nombre_feature=args.recalcular_feature.decode('utf-8'))
        elif args.calcular_features_faltantes:
            features_obj = Features(args.threads)
            features_obj.calcular_features_faltantes(corpus)
            guardar_features(corpus)
        else:
            features_obj = None

        no_dudosos = filtrar_segun_votacion(corpus)
        dudosos = [tweet for tweet in corpus if tweet not in no_dudosos]
        corpus = list(no_dudosos)

        if args.solo_subcorpus_humor:
            corpus = [tweet for tweet in corpus if tweet.es_chiste]

        if args.subconjunto_no_humor:
            corpus = [tweet for tweet in corpus if tweet.es_humor or tweet.categoria == args.subconjunto_no_humor[0]]

        if args.tweets_parecidos_distinto_humor:
            pares_parecidos_con_distinto_humor = tweets_parecidos_con_distinto_humor(corpus)
            parecidos_con_distinto_humor = {tweet
                                            for par_parecido in pares_parecidos_con_distinto_humor
                                            for tweet in par_parecido}
            corpus = [tweet for tweet in corpus if tweet not in parecidos_con_distinto_humor]

        if args.mismas_features_distinto_humor:
            mismas_features_distinto_humor = mismas_features_distinto_humor(corpus)

        if args.evaluar:
            entrenamiento = [tweet for tweet in corpus if not tweet.evaluacion]
            evaluacion = [tweet for tweet in corpus if tweet.evaluacion]
        else:
            corpus = [tweet for tweet in corpus if not tweet.evaluacion]
            entrenamiento, evaluacion = train_test_split_pro(corpus, test_size=0.2)

        if args.reportar_informacion_corpus:
            print('')
            print("Conformación del corpus:")
            print('')
            print("                 entrenamiento evaluacion total")
            print("    Humor        {he}          {ht}       {htot}".format(
                he=sum(1 for tweet in entrenamiento if tweet.es_humor),
                ht=sum(1 for tweet in evaluacion if tweet.es_humor),
                htot=sum(1 for tweet in corpus if tweet.es_humor)
            ))
            print("    No humor     {nhe}         {nht}       {nhtot}".format(
                nhe=sum(1 for tweet in entrenamiento if not tweet.es_humor),
                nht=sum(1 for tweet in evaluacion if not tweet.es_humor),
                nhtot=sum(1 for tweet in corpus if not tweet.es_humor)
            ))
            print("    Total        {te}         {tt}       {t}".format(
                te=len(entrenamiento),
                tt=len(evaluacion),
                t=len(corpus)
            ))
            print('')

        if args.grupo_de_calificacion:
            evaluacion = [tweet for tweet in evaluacion
                          if not tweet.promedio_de_humor or not tweet.es_humor
                          or args.grupo_de_calificacion - 0.5 <= tweet.promedio_de_humor
                          < args.grupo_de_calificacion + 0.5]

        if args.feature_aleatoria:
            for tweet in corpus:
                tweet.features["ALEATORIA"] = random.uniform(0, 1)

        if args.feature_clase:
            for tweet in corpus:
                tweet.features["CLASE"] = tweet.es_humor

        if not args.rfe:
            # Features que remueve RFE:
            for tweet in corpus:
                del tweet.features["Palabras no españolas"]
                del tweet.features["Negacion"]
                # del tweet.features["Antonimos"]  # No la sacamos porque ya hicimos el análisis así.

            if args.dudosos:
                for tweet in dudosos:
                    del tweet.features["Palabras no españolas"]
                    del tweet.features["Negacion"]
                    # del tweet.features["Antonimos"]

        clases = get_clases(corpus)
        clases_entrenamiento = get_clases(entrenamiento)
        clases_evaluacion = get_clases(evaluacion)

        if args.clasificador == "LB1":
            features = corpus
            features_entrenamiento = entrenamiento
            features_evaluacion = evaluacion
        else:
            features = get_features(corpus)
            features_entrenamiento = get_features(entrenamiento)
            features_evaluacion = get_features(evaluacion)

        if args.dudosos:
            features_dudosos = get_features(dudosos)

        # Se tiene que hacer antes del scaler (las features no puden tomar valores negativos)
        if args.importancias_features:
            nombres_features_ordenadas = corpus[0].nombres_features_ordenadas()
            tree_based_feature_selection(features, clases, nombres_features_ordenadas)
            chi2_feature_selection(features, clases, nombres_features_ordenadas)
            f_score_feature_selection(features, clases, nombres_features_ordenadas)

        if not args.sin_escalar and args.clasificador != "MNB" \
                and args.clasificador != "LB1" and args.clasificador != "LB2":
            scaler = preprocessing.StandardScaler().fit(features_entrenamiento)
            features = scaler.transform(features)
            features_entrenamiento = scaler.transform(features_entrenamiento)
            features_evaluacion = scaler.transform(features_evaluacion)

            if args.dudosos:
                features_dudosos = scaler.transform(features_dudosos)

        if args.rfe:
            rfecv = RFECV(estimator=svm.SVC(kernel=str('linear')), cv=5, scoring='accuracy', verbose=3)
            rfecv.fit(features_entrenamiento, clases_entrenamiento)

            print("Número óptimo de featues: {n_features}".format(n_features=rfecv.n_features_))

            nombres_features_ordenadas = corpus[0].nombres_features_ordenadas()
            imprimir_importancias(rfecv.ranking_, "RFECV", nombres_features_ordenadas)

            # Esto saca "Palabras no españolas" y "Negación". La última vez también sacó "Antónimos".

            import matplotlib.pyplot as plt

            plt.figure()
            plt.xlabel("Número de características seleccionadas")
            plt.ylabel("Acierto")
            plt.plot(range(1, len(rfecv.grid_scores_) + 1), rfecv.grid_scores_)
            plt.show()

            plt.figure()
            plt.xlabel("Número de características seleccionadas")
            plt.ylabel("Acierto")
            plt.autoscale(enable=False, axis='y')
            plt.plot(range(1, len(rfecv.grid_scores_) + 1), rfecv.grid_scores_)
            plt.show()

        parameters_grid_search = {}
        if args.clasificador == "DT":
            clasificador_usado = tree.DecisionTreeClassifier()
            parameters_grid_search = parameters_dt
        elif args.clasificador == "GNB":
            clasificador_usado = naive_bayes.GaussianNB()
            parameters_grid_search = parameters_gnb
        elif args.clasificador == "kNN":
            clasificador_usado = neighbors.KNeighborsClassifier()
            parameters_grid_search = parameters_knn
        elif args.clasificador == "LinearSVM":
            clasificador_usado = svm.LinearSVC()
        elif args.clasificador == "LB1":
            feature_union = FeatureUnion([
                ('vectorizer_bow', Pipeline([
                    ('tweet_to_text', TweetToText()),
                    ('vectorizer', CountVectorizer(
                        strip_accents='ascii',
                        stop_words=get_stop_words(),
                        token_pattern=r'\b[a-z0-9_\-\.]+[a-z][a-z0-9_\-\.]+\b',
                    ))
                ])),
                ('features_tweets', TweetsToFeatures()),
            ])

            clasificador_usado = Pipeline([
                ('features', feature_union),
                ('clf', naive_bayes.MultinomialNB(alpha=0.01)),
            ])
        elif args.clasificador == "LB2":
            clasificador_usado = Mayoria()
        elif args.clasificador == "MNB":
            clasificador_usado = naive_bayes.MultinomialNB()
            parameters_grid_search = parameters_mnb
        elif args.clasificador == "SGD":
            clasificador_usado = linear_model.SGDClassifier(shuffle=True)
        else:  # "SVM"
            clasificador_usado = svm.SVC()
            parameters_grid_search = parameters_svm

        if args.grid_search:
            grid_search = GridSearchCV(clasificador_usado, parameters_grid_search, cv=5, verbose=2, n_jobs=8)

            grid_search.fit(features, clases)
            print("Mejores parámetros encontrados para " + args.clasificador + ":")
            for nombre_parametro, valor_parametro in clasificador_usado.get_params().items():
                print("\t{clave}: {valor}".format(clave=nombre_parametro, valor=valor_parametro))
            print('')
            print("Acierto: {acierto}".format(acierto=grid_search.best_score_))
            grid_search.best_estimator_ = grid_search.best_estimator_.fit(features, clases)
            clasificador_usado = grid_search.best_estimator_
            print('')

        if args.parametros_clasificador:
            print('')
            print("Parametros del clasificador:")
            for nombre_parametro, valor_parametro in clasificador_usado.get_params().items():
                print("\t{clave}: {valor}".format(clave=nombre_parametro, valor=valor_parametro))
            print('')

        if args.cross_validation and not args.evaluar:
            cross_validation_y_reportar(clasificador_usado, features, clases, 5)

        print("Entrenando clasificador...")
        if args.ponderar_segun_votos:
            if args.clasificador == "SVM":
                sample_weights = [1 - entropia(tweet.votos_humor / tweet.votos) if tweet.votos > 0 else 1
                                  for tweet in entrenamiento]
                clasificador_usado.fit(features_entrenamiento, clases_entrenamiento, sample_weight=sample_weights)
            elif args.clasificador == "DT":
                sample_weights = [1 - 2 * entropia(tweet.votos_humor / tweet.votos) if tweet.votos > 0 else 1
                                  for tweet in entrenamiento]
                clasificador_usado.fit(features_entrenamiento, clases_entrenamiento, sample_weight=sample_weights)
            else:
                clasificador_usado.fit(features_entrenamiento, clases_entrenamiento)
        else:
            clasificador_usado.fit(features_entrenamiento, clases_entrenamiento)

        if args.ponderar_segun_votos:
            medidas_ponderadas = "concordancia"
        else:
            medidas_ponderadas = ""

        print("Evaluando clasificador con el conjunto de entrenamiento...")
        clases_predecidas_entrenamiento = clasificador_usado.predict(features_entrenamiento)
        matriz_de_confusion_y_reportar(entrenamiento, clases_entrenamiento, clases_predecidas_entrenamiento,
                                       medidas_ponderadas)

        print("Evaluando clasificador...")
        print('')
        clases_predecidas = clasificador_usado.predict(features_evaluacion)
        if args.medidas_ponderadas:
            mostrar_medidas_ponderadas(evaluacion, clases_evaluacion, clases_predecidas)
        matriz_de_confusion_y_reportar(evaluacion, clases_evaluacion, clases_predecidas, medidas_ponderadas)

        if args.dudosos:
            clases_predecidas_dudosos = clasificador_usado.predict(features_dudosos)

            cantidad_de_dudosos_de_humor = sum(clases_predecidas_dudosos)
            print("Porcentaje de dudosos clasificados como positivos: {dudosos_humor:0.4f}".format(
                dudosos_humor=cantidad_de_dudosos_de_humor / len(clases_predecidas_dudosos)))

        if args.servidor:
            app = Flask(__name__)

            if not features_obj:
                features_obj = Features(args.threads)

                # Features que remueve RFE:
                del features_obj.features["Palabras no españolas"]
                del features_obj.features["Negacion"]
                # del features_obj.features["Antonimos"]

            @app.route("/")
            def inicio():
                return app.send_static_file('evaluacion.html')

            @app.route("/evaluar", methods=['POST'])
            @cross_origin()
            def evaluar():
                _tweet = Tweet()
                _tweet.texto = request.form['texto']
                _tweet.preprocesar()

                features_obj.calcular_features([_tweet])
                _features = [_tweet.array_features()]
                return flask.jsonify(
                    {
                        'humor': unicode(int(clasificador_usado.predict(_features)[0])),
                        'features': _tweet.features,
                    })

            app.run(host='0.0.0.0')  # debug=True,
