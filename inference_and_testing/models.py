# generative model for reviews
# this version is used to generate the histogram of reviews for a particular product over time, irrespective of the
# choice of a particular product among many. There is a single decision to purchase or not to purchase that each consumer
# faces, followed by a decision to leave a review or not.
# The parameters are the parameters of a single product.

import settings
import random as RD
import numpy as np
import scipy.stats as st
import copy


RD.seed()


class product():

    def __init__(self):
        self.set_missing_product_params()

    def set_missing_product_params(self):
        # if 'product_indices' not in  self.fixed_params: # product indices not useful for just one product.
        #     self.params['product_indices'] = list(range(self.params['number_of_products']))
        if 'number_of_rating_levels' not in self.fixed_params:
            self.params['number_of_rating_levels'] = 5
        if 'price' not in self.fixed_params:
            self.params['price'] = 10
        if 'product_features' not in self.fixed_params:
            self.params['product_features'] = dict.fromkeys(['feature'])
            self.params['product_features']['feature'] = [20]
        if 'neutral_quality' not in self.fixed_params:
            self.params['neutral_quality'] = 3
        if 'quality_std' not in self.fixed_params:
            self.params['quality_std'] = 1.5
        if 'true_quality' not in self.fixed_params:
            self.params['true_quality'] = np.random.normal(self.params['neutral_quality'],
                                                           self.params['quality_std'])
        if 'product_tracked' not in self.fixed_params:
            self.params['product_tracked'] = 0  # the product whose histograms we ae analyzing

        if 'input_type' not in self.fixed_params:
            self.params['input_type'] = 'histograms'#'averages'  # train the network with the average of reviews rather than
            # the full histogram of reviews

        if 'input_histograms_are_normalized' not in self.fixed_params:
            self.params['input_histograms_are_normalized'] = False  # histograms are normalized to the frequencies
            # rather than showing the total counts
        if 'value_of_outside_option' not in self.fixed_params:
            self.params['value_of_outside_option'] = 0.0  # Whenever the expected utility exceeds the value of the
            # outside option, the product is purchased.
        if 'testing_what' not in self.fixed_params:
            self.params['testing_what'] = 'threshold_directionality'  # We can either test for BM vs Motivation or test
            # for threshold_positive_zero or use ABC to determine threshold_directionality


class consumer(product):
    def __init__(self):
        super(consumer, self).__init__()
        self.set_missing_consumer_params()

    def set_missing_consumer_params(self):
        if 'tendency_to_rate' not in self.fixed_params:
            self.params['tendency_to_rate'] = 0.2
        if 'number_of_rating_levels' not in self.fixed_params:
            self.params['number_of_rating_levels'] = 5
        if 'consumer_fit_std' not in self.fixed_params:
            self.params['consumer_fit_std'] = 4.5
        if 'consumer_fit_distribution' not in self.fixed_params:
            self.params['consumer_fit_distribution'] = st.norm(0, self.params['consumer_fit_std'])

        # if 'consumer_comparison_mode' not in self.fixed_params:
        #     self.params['consumer_comparison_mode'] should not be set here, it should be set in set_random_params
        # because it is the subject of inference.

    def init_consumer_private_parameters(self):
        self.consumer_private_fit = self.params['consumer_fit_distribution'].rvs()
        self.consumer_private_alpha = np.random.normal(self.params['population_alpha'][0],
                                                       self.params['population_alpha'][1])
        self.consumer_private_beta = dict.fromkeys(self.params['population_beta'].keys())
        for i in self.params['population_beta'].keys():
            self.consumer_private_beta[i] = np.random.normal(self.params['population_beta'][i][0],
                                                             self.params['population_beta'][i][1])

    def make_purchase(self):
        product_is_purchased = False

        features_utility = 0
        for i in self.params['product_features'].keys():
            features_utility += self.consumer_private_beta[i + '_beta'] * np.array(self.params['product_features'][i])

        price_utility = self.consumer_private_alpha * np.array(self.params['price'])

        expected_utility = features_utility + price_utility + self.percieved_qualities[-1] + self.consumer_private_fit

        # print(expected_utility)
        if expected_utility > self.params['value_of_outside_option']:
            product_is_purchased = True
        # print(product_is_purchased)
        return product_is_purchased

    def evaluate_product(self):

        if self.params['consumer_comparison_mode'] == 'BM':
            review_levels = [self.percieved_qualities[-1] - 1.5, self.percieved_qualities[-1] - 0.5,
                             self.percieved_qualities[-1] + 0.5,
                             self.percieved_qualities[-1] + 1.5]

            experienced_quality = self.params['true_quality'] + self.consumer_private_fit

            product_review = int(1 + sum(1.0 * (experienced_quality >= np.array(review_levels))))
            print(experienced_quality)
            print(np.array(review_levels))
            # print(self.params['consumer_comparison_mode'])

        elif self.params['consumer_comparison_mode'] == 'motivation':

            if self.avg_reviews:  # it is not the first review, avg_reviews is not an empty list
                review_levels = [self.avg_reviews[-1] - 1.5, self.avg_reviews[-1] - 0.5,
                                 self.avg_reviews[-1] + 0.5, self.avg_reviews[-1] + 1.5]
            else:
                review_levels = [self.params['neutral_quality'] - 1.5, self.params['neutral_quality'] - 0.5,
                                 self.params['neutral_quality'] + 0.5, self.params['neutral_quality'] + 1.5]

            experienced_quality = self.params['true_quality'] + self.consumer_private_fit
            # print('true_quality',self.params['true_quality'])

            product_review = int(1 + sum(1.0 * (experienced_quality >= np.array(review_levels))))

            # print(self.params['consumer_comparison_mode'])

        else:
            raise Exception("consumer_comparison_mode not set!")

        return product_review

        review_levels = [self.percieved_qualities[-1] - 1.5, self.percieved_qualities[-1] - 0.5,
                         self.percieved_qualities[-1] + 0.5,
                         self.percieved_qualities[-1] + 1.5]

        experienced_quality = self.params['true_quality'] + self.consumer_private_fit

        product_review = int(1 + sum(1.0 * (experienced_quality >= np.array(review_levels))))

        return product_review

    def decide_to_rate(self, product_review):

        if self.params['consumer_comparison_mode'] == 'BM':
            if np.random.binomial(1, self.params['tendency_to_rate']):
                decision = True
            elif self.avg_reviews:  # it is not the first review, avg_reviews is not an empty list
                decision = ((((product_review - self.percieved_qualities[-1]) >
                              self.params['rate_decision_threshold_above']) or
                             ((product_review - self.percieved_qualities[-1]) <
                              (-1.0)*self.params['rate_decision_threshold_below']))
                            and (np.random.binomial(1, min(3 * self.params['tendency_to_rate'], 1))))
            else:
                decision = True

            # print(self.params['consumer_comparison_mode'],decision)

        if self.params['consumer_comparison_mode'] == 'motivation':
            if np.random.binomial(1, self.params['tendency_to_rate']):
                decision = True
            elif self.avg_reviews:  # it is not the first review, avg_reviews is not an empty list
                decision = ((((product_review - self.avg_reviews[-1]) >
                              self.params['rate_decision_threshold_above']) or
                             ((product_review - self.avg_reviews[-1]) <
                              (-1.0)*self.params['rate_decision_threshold_below']))
                            and (np.random.binomial(1, min(3 * self.params['tendency_to_rate'], 1))))
            else:
                decision = True

            # print(self.params['consumer_comparison_mode'],decision)

        return decision


class market(consumer):
    def __init__(self, params={}):
        self.fixed_params = copy.deepcopy(params)
        self.params = copy.deepcopy(params)
        self.set_missing_market_params()
        super(market, self).__init__()

    def set_missing_market_params(self):
        if 'population_beta' not in self.fixed_params:
            self.params['population_beta'] = dict.fromkeys(['feature_beta'])
            self.params['population_beta']['feature_beta'] = [np.random.uniform(1, 2), 1]
        if 'population_alpha' not in self.fixed_params:
            self.params['population_alpha'] = [np.random.uniform(-3, -2), 1]
        if 'total_number_of_reviews' not in self.fixed_params:
            self.params['total_number_of_reviews'] = 100

    def set_random_params(self, theta_above=None, theta_below=None):
        """Randomly sets the parameters that are the subject of inference by the inference engine.
        The parameters are randomized according to the prior distributions"""
        if theta_below is None:
            theta_below = theta_above
        if self.params['testing_what'] == 'BM vs Motivation':
            self.params['consumer_comparison_mode'] = RD.choice(['BM', 'motivation'])
            if 'rate_decision_threshold_above' not in self.fixed_params:
                self.params['rate_decision_threshold_above'] = 1
                self.params['rate_decision_threshold_below'] = self.params['rate_decision_threshold_above']
        elif self.params['testing_what'] == 'threshold_positive_zero':
            self.params['rate_decision_threshold_above'] = RD.choice([-1.0, 1.0])
            self.params['rate_decision_threshold_below'] = self.params['rate_decision_threshold_above']
            if 'consumer_comparison_mode' not in self.fixed_params:
                self.params['consumer_comparison_mode'] = 'motivation'
        elif self.params['testing_what'] == 'threshold_fixed':
            self.params['rate_decision_threshold_above'] = 1.0
            self.params['rate_decision_threshold_below'] = self.params['rate_decision_threshold_above']
            if 'consumer_comparison_mode' not in self.fixed_params:
                self.params['consumer_comparison_mode'] = 'motivation'
        elif self.params['testing_what'] == 'threshold_directionality':
            assert theta_above is not None, "theta not supplied for threshold_directionality"
            self.params['rate_decision_threshold_above'] = theta_above
            self.params['rate_decision_threshold_below'] = theta_below
            if 'consumer_comparison_mode' not in self.fixed_params:
                self.params['consumer_comparison_mode'] = 'motivation'
        elif self.params['testing_what'] == 'acquisition_bias': # in this mode all customers review irrespective of
            # whether they buy or decide_to_rate is True or False
            self.params['rate_decision_threshold_above'] = 0.0
            self.params['rate_decision_threshold_below'] = self.params['rate_decision_threshold_above']
            if 'consumer_comparison_mode' not in self.fixed_params:
                self.params['consumer_comparison_mode'] = 'motivation'
        else:
            raise Exception("testing_what is undefined!")

    def init_reputation_dynamics(self):

        self.percieved_qualities = []
        self.reviews = []
        self.avg_reviews = []
        self.histogram_reviews = [0] * self.params['number_of_rating_levels']
        self.percieved_qualities = []
        self.avg_reviews_all_consumers = []  # the avg review that each consumer observes will have the same length as
        # the perceived quality
        self.fit_of_customers_who_put_reviews = []  # records the the fit signal for each consumer
        # who puts  review, have the same length as the reviews or avg_reviews time series

        self.customer_count = 0
        self.purchase_decisions = []
        self.purchase_count = 0

    def form_perception_of_quality(self):
        if self.avg_reviews:
            quality_anchor = self.avg_reviews[-1]
        else:
            quality_anchor = self.params['neutral_quality']

        observed_histograms = self.histogram_reviews

        # infer_quality = mc.Normal('infer_quality', mu=self.params['neutral_quality'],
        #                          tau=self.params['quality_std'])  # this is the prior on the quality

        infer_quality = np.linspace(-1.0, 8.0, 1000)  # assume quality is between -1 and 8 (1000 bins in between)
        log_prior = np.log(st.norm.pdf(infer_quality, loc=self.params['neutral_quality'], scale=self.params[
            'quality_std']))  # evaluate prior by plugging in above values to PDF (take log for ease of underflow errors: small numbers problem)

        data = observed_histograms
        # quality anchor is fixed. 4 values of interest:
        # quality anchor - (0.5 + infer_qual); quality anchor - (1.5 + infer_qual);
        # quality anchor + (0.5 - infer_qual); quality anchor + (1.5 - infer_qual)
        # form two vectors, each with 2 rows, based on the above definition
        # then, evaluate the cdf part by part by utilising these values -
        # reduces recomputing same estimates and speeds up calculation
        consumer_fit_test_vals1 = np.tile(np.array([0.5, 1.5]).reshape(2, 1), (1, infer_quality.shape[0])) + np.tile(
            infer_quality.reshape(1, infer_quality.shape[0]), (2, 1))
        consumer_fit_test_vals2 = np.tile(np.array([0.5, 1.5]).reshape(2, 1), (1, infer_quality.shape[0])) - np.tile(
            infer_quality.reshape(1, infer_quality.shape[0]), (2, 1))
        consumer_fit_cdf1 = self.params['consumer_fit_distribution'].cdf(quality_anchor - consumer_fit_test_vals1)
        consumer_fit_cdf2 = self.params['consumer_fit_distribution'].cdf(quality_anchor + consumer_fit_test_vals2)
        # if we take the vector log_prior, we can perform the operation of +- etc to the WHOLE vector instead of taking point by point evaluations and summing

        log_likelihood = np.log(consumer_fit_cdf1[1, :]) * data[0] + \
                         np.log(consumer_fit_cdf1[0, :] - consumer_fit_cdf1[1, :]) * data[1] + \
                         np.log(consumer_fit_cdf2[0, :] - consumer_fit_cdf1[0, :]) * data[2] + \
                         np.log(consumer_fit_cdf2[1, :] - consumer_fit_cdf2[0, :]) * data[3] + \
                         np.log(1 - consumer_fit_cdf2[1, :]) * data[4]
        posterior = np.exp(log_prior + log_likelihood)

        # print(np.sum(posterior))

        self.percieved_qualities += [np.sum(posterior * infer_quality / np.sum(posterior))]
        assert not np.isnan(self.percieved_qualities[-1]), "perceived quality is nan!"
        self.avg_reviews_all_consumers += [quality_anchor]

    def step(self):
        self.init_consumer_private_parameters()
        # fixing the common prior on quality at the beginning of perception:
        if 'neutral_quality' not in self.fixed_params:
            self.params['neutral_quality'] = 3.0
        else:
            self.params['neutral_quality'] = self.fixed_params['neutral_quality']
        self.form_perception_of_quality()
        product_is_purchased = self.make_purchase()
        self.purchase_count += product_is_purchased * 1.0
        self.purchase_decisions.append(product_is_purchased)
        product_review = self.evaluate_product()

        if self.params['testing_what'] == 'acquisition_bias':  # all customers review irrespective of
            # whether they buy or decide_to_rate is True or False
            self.reviews.append(product_review)
            self.avg_reviews.append(np.mean(self.reviews))
            self.histogram_reviews[product_review - 1] += 1
            self.fit_of_customers_who_put_reviews.append(self.consumer_private_fit)
            a_product_is_reviewed = True
        elif product_is_purchased and self.decide_to_rate(product_review):
            self.reviews.append(product_review)
            self.avg_reviews.append(np.mean(self.reviews))
            self.histogram_reviews[product_review - 1] += 1
            self.fit_of_customers_who_put_reviews.append(self.consumer_private_fit)
            a_product_is_reviewed = True
        else:
            a_product_is_reviewed = False

        self.customer_count += 1

        return a_product_is_reviewed

    def generateTimeseries(self, theta=None, raw=False,
                           fix_population_size=False, population_size=None,
                           get_percieved_qualities_and_avg_reviews=True,
                           get_fit_of_customers_who_put_reviews=False,
                           do_not_return_df=False): # for threshold_postive_zero, theta not needed
        assert ((fix_population_size and population_size is not None) or
                ((not fix_population_size) and population_size is None)), "fix_population_size and population_size " \
                                                                          "are not properly set."

        # conditioned on the fixed_params
        self.set_random_params(theta)  # The random parameter that is the subject of inference is set here.
        # This parameter determines the true label for the generated time series (example).
        # The distribution according to which the parameter is randomized is our prior on it

        self.init_reputation_dynamics()
        timeseries = []

        continue_while = True

        while continue_while:
            a_product_is_reviewed = self.step()

            if a_product_is_reviewed:
                if raw: # this is used for ABC
                    timeseries.append(self.reviews[-1])
                elif self.params['input_type'] == 'averages':
                    timeseries.append(self.avg_reviews[-1])
                elif self.params['input_type'] == 'histograms':
                    histogram = copy.deepcopy(self.histogram_reviews)
                    if self.params['input_histograms_are_normalized'] and (sum(histogram) > 0):
                        histogram = list(np.array(histogram) / (1.0 * sum(histogram)))
                    timeseries.append(histogram)
                elif self.params['input_type'] == 'kurtosis':
                    histogram = copy.deepcopy(self.histogram_reviews)
                    if sum(histogram) > 0:
                        histogram = list(np.array(histogram) / (1.0 * sum(histogram)))
                    kurtosis = st.kurtosis(histogram, fisher=False, bias=True)
                    timeseries.append(kurtosis)
            if not fix_population_size:
                continue_while = len(timeseries) < self.params['total_number_of_reviews']
            else:
                continue_while = self.customer_count < population_size
        #
        # print(self.customer_count)
        # print(self.purchase_count)
        # print(len(timeseries))

        if do_not_return_df:
            df = timeseries
        else:
            df = pd.DataFrame(timeseries)


        if get_percieved_qualities_and_avg_reviews and get_fit_of_customers_who_put_reviews:
            return df, self.avg_reviews_all_consumers, self.percieved_qualities,self.fit_of_customers_who_put_reviews
        elif get_percieved_qualities_and_avg_reviews and not get_fit_of_customers_who_put_reviews:
            return df, self.avg_reviews_all_consumers, self.percieved_qualities
        else:
            return df

    def compute_direction_probability(self, dataset_size = 500):
        ''' Returns the probability of putting a review above average. Probability of putting a review below threshld is
        1 - probability of putting a review below average. The average is computed for dataset_size samples. Each sample
        is generated with theta drawn independently uniformly at random from the vector prior_theta. '''
        fractions_above = []
        # print(self.prior)
        assert hasattr(self, 'prior'), "prior undefined!!"
        for i in range(dataset_size):
            theta = np.random.choice(self.prior)
            raw_timeseries = self.generate_data(theta)
            raw_averages = []
            for ii in range(1, len(raw_timeseries) + 1):
                raw_averages.append(np.mean(raw_timeseries[:ii]))

            count_aboves = 0
            for i in range(1, len(raw_timeseries)):
                if raw_timeseries[i] > raw_averages[i - 1]:
                    count_aboves += 1
            # print(count_aboves)
            fractions_above += [count_aboves/(1.0*len(raw_timeseries))]
            # print(fractions_above)
        fraction_above = np.mean(fractions_above)
        # print(fraction_above)
        return fraction_above

    def genTorchSample(self):
        # implement these if neural network in inference not for ABC
        pass

    def genTorchDataset(self, dataset_size=1000, filename='dataset.pkl', LOAD=False, SAVE=False):
        # implement these if neural network in inference not for ABC
        pass
