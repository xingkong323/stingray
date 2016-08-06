import numpy as np
import scipy.stats

from astropy.tests.helper import pytest
from astropy.modeling import models

from stingray import Lightcurve, Powerspectrum
from stingray.modeling import Posterior, PSDPosterior
from stingray.modeling import set_logprior
from stingray.modeling.posterior import logmin

np.random.seed(20150907)

class TestSetPrior(object):

    @classmethod
    def setup_class(cls):
        photon_arrivals = np.sort(np.random.uniform(0,1000, size=10000))
        cls.lc = Lightcurve.make_lightcurve(photon_arrivals, dt=1.0)
        cls.ps = Powerspectrum(cls.lc, norm="frac")
        pl = models.PowerLaw1D()
        cls.lpost = PSDPosterior(cls.ps, pl)

    def test_set_prior_runs(self):
        p_alpha = lambda alpha: ((-1. <= alpha) & (alpha <= 5.))/6.0
        p_amplitude = lambda amplitude: ((-10 <= np.log(amplitude)) &
                                         ((np.log(amplitude) <= 10.0)))/20.0

        priors = {"alpha":p_alpha, "amplitude":p_amplitude}
        self.lpost.logprior = set_logprior(self.lpost, priors)

    def test_prior_executes_correctly(self):
        p_alpha = lambda alpha: ((-1. <= alpha) & (alpha <= 5.))/6.0
        p_amplitude = lambda amplitude: ((-10 <= np.log(amplitude)) &
                                         ((np.log(amplitude) <= 10.0)))/20.0

        priors = {"alpha":p_alpha, "amplitude":p_amplitude}
        self.lpost.logprior = set_logprior(self.lpost, priors)
        true_logprior = np.log(1./6.) + np.log(1./20.0)
        assert self.lpost.logprior([0.0, 0.0]) ==  true_logprior

    def test_prior_returns_logmin_outside_prior_range(self):
        p_alpha = lambda alpha: ((-1. <= alpha) & (alpha <= 5.))/6.0
        p_amplitude = lambda amplitude: ((-10 <= np.log(amplitude)) &
                                         ((np.log(amplitude) <= 10.0)))/20.0

        priors = {"alpha":p_alpha, "amplitude":p_amplitude}
        self.lpost.logprior = set_logprior(self.lpost, priors)
        assert self.lpost.logprior([0.0, 0.0]) ==  2*logmin


class PosteriorClassDummy(Posterior):
    """
    This is a test class that tests the basic functionality of the
    Posterior superclass.
    """
    def __init__(self, x, y, model):
        Posterior.__init__(self, x, y, model)

    def  loglikelihood(self, t0, neg=False):
        loglike = 1.0
        return loglike

    def logprior(self, t0):
        lp = 2.0
        return lp

class TestPosterior(object):

    @classmethod
    def setup_class(cls):
        cls.x = np.arange(100)
        cls.y = np.ones(cls.x.shape[0])
        cls.model = models.Const1D()
        cls.p = PosteriorClassDummy(cls.x, cls.y, cls.model)
        p_alpha = lambda alpha: ((-1. <= alpha) & (alpha <= 5.))/6.0

        priors = {"alpha":p_alpha}
        cls.p.logprior = set_logprior(cls.p, priors)

    def test_inputs(self):
        assert np.allclose(self.p.x, self.x)
        assert np.allclose(self.p.y, self.y)
        assert isinstance(self.p.model, models.Const1D)

    def test_call_method_positive(self):
        t0 = [1,2,3]
        post = self.p(t0, neg=False)
        assert post == 3.0

    def test_call_method_negative(self):
        t0 = [1,2,3]
        post = self.p(t0, neg=True)
        assert post == -3.0


class TestPSDPosterior(object):

    @classmethod
    def setup_class(cls):
        m = 1
        nfreq = 1000000
        freq = np.arange(nfreq)
        noise = np.random.exponential(size=nfreq)
        power = noise*2.0

        ps = Powerspectrum()
        ps.freq = freq
        ps.power = power
        ps.m = m
        ps.df = freq[1]-freq[0]
        ps.norm = "leahy"

        cls.ps = ps
        cls.a_mean, cls.a_var = 2.0, 1.0

        cls.model = models.Const1D()
        cls.p = PosteriorClassDummy(ps.freq, ps.power, cls.model)

        p_alpha = lambda amean, avar: scipy.stats.norm(loc=amean,
                                                       scale=avar)

        priors = {"alpha":p_alpha}
        cls.p.logprior = set_logprior(cls.p, priors)

    def test_logprior_fails_without_prior(self):
        model = models.Const1D()
        lpost = PSDPosterior(self.ps, model)
        with pytest.raises(AssertionError):
            lpost.logprior([1])

    def test_making_posterior(self):
        lpost = PSDPosterior(self.ps, self.model)
        assert lpost.x.all() == self.ps.freq.all()
        assert lpost.y.all() == self.ps.power.all()

    def test_correct_number_of_parameters(self):
        lpost = PSDPosterior(self.ps, self.model)
        with pytest.raises(AssertionError):
            lpost([2,3])

    def test_logprior(self):
        t0 = [2.0]

        lpost = PSDPosterior(self.ps, self.model)
        lp_test = lpost.logprior(t0)
        lp = np.log(scipy.stats.norm(2.0, 1.0).pdf(t0))
        assert lp == lp_test

    def test_loglikelihood(self):
        t0 = [2.0]
        m = self.model(self.ps.freq[1:], t0)
        loglike = -np.sum(self.ps.power[1:]/m + np.log(m))

        lpost = PSDPosterior(self.ps, self.model)
        loglike_test = lpost.loglikelihood(t0, neg=False)

        assert np.isclose(loglike, loglike_test)

    def test_loglikelihood_correctly_leaves_out_zeroth_freq(self):
        t0 = [2.0]
        m = self.model(self.ps.freq, t0)
        loglike = -np.sum(self.ps.power/m + np.log(m))

        lpost = PSDPosterior(self.ps, self.model)
        loglike_test = lpost.loglikelihood(t0, neg=False)

        with pytest.raises(AssertionError):
            assert np.isclose(loglike_test, loglike, atol=1.e-10, rtol=1.e-10)

    def test_negative_loglikelihood(self):
        t0 = [2.0]
        m = self.model(self.ps.freq[1:], t0)
        loglike = np.sum(self.ps.power[1:]/m + np.log(m))

        lpost = PSDPosterior(self.ps, self.model)
        loglike_test = lpost.loglikelihood(t0, neg=True)

        assert np.isclose(loglike, loglike_test)

    def test_posterior(self):
        t0 = [2.0]
        m = self.model(self.ps.freq[1:], t0)
        lpost = PSDPosterior(self.ps, self.model)
        post_test = lpost(t0, neg=False)

        loglike = -np.sum(self.ps.power[1:]/m + np.log(m))
        logprior = np.log(scipy.stats.norm(2.0, 1.0).pdf(t0))
        post = loglike + logprior

        assert np.isclose(post_test, post, atol=1.e-10)

    def test_negative_posterior(self):
        t0 = [2.0]
        m = self.model(self.ps.freq[1:], t0)
        lpost = PSDPosterior(self.ps, self.model)
        post_test = lpost(t0, neg=True)

        loglike = -np.sum(self.ps.power[1:]/m + np.log(m))
        logprior = np.log(scipy.stats.norm(2.0, 1.0).pdf(t0))
        post = -loglike - logprior

        assert np.isclose(post_test, post, atol=1.e-10)

class TestPerPosteriorAveragedPeriodogram(object):

    @classmethod
    def setup_class(cls):

        m = 10
        nfreq = 1000000
        freq = np.arange(nfreq)
        noise = scipy.stats.chi2(2.*m).rvs(size=nfreq)/np.float(m)
        power = noise

        ps = Powerspectrum()
        ps.freq = freq
        ps.power = power
        ps.m = m
        ps.df = freq[1]-freq[0]
        ps.norm = "leahy"

        cls.ps = ps
        cls.a_mean, cls.a_var = 2.0, 1.0

        cls.model = models.Const1D()

    def test_likelihood(self):
        t0 = [2.0]
        m = self.model(self.ps.freq[1:], t0)
        ## TODO: Finish this test!

## TODO: Write tests for Lightcurve posterior
## TODO: Write tests for Gaussian posterior
