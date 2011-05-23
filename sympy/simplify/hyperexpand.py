"""
Expand Hypergeometric (and Meijer G) functions into named
special functions.

The algorithm for doing this uses a collection of lookup tables of
hypergeometric functions, and various of their properties, to expand
many hypergeometric functions in terms of special functions.

It is based on the following paper:
      Kelly B. Roach.  Meijer G Function Representations.
      In: Proceedings of the 1997 International Symposium on Symbolic and
      Algebraic Computation, pages 205-211, New York, 1997. ACM.

It is described in great(er) detail in the Sphinx documentation.
"""
from sympy.core import S, Dummy, symbols, sympify, Tuple, expand, I, Mul

def add_formulae(formulae):
    """ Create our knowledge base.
        Leave this at the top for easy reference. """
    z = Dummy('z')
    a, b, c = symbols('a b c', cls=Dummy)
    def add(ap, bq, res):
        formulae.append(Formula(ap, bq, z, res, (a, b, c)))
    def addb(ap, bq, B, C, M):
        formulae.append(Formula(ap, bq, z, None, (a, b, c), B, C, M))

    from sympy.matrices import diag, Matrix

    # Luke, Y. L. (1969), The Special Functions and Their Approximations,
    # Volume 1, section 6.2

    from sympy import exp, sqrt, cosh, log, asin, atan, I
    add((), (), exp(z))
    add((-a, ), (), (1-z)**a)
    add((a, a - S.Half), (2*a,), (S.Half + sqrt(1 - z)/2)**(1-2*a))
    add((), (S.Half,), cosh(2*sqrt(z)))
    add((1, 1), (2,), log(1 - z)/-z)
    add((S.Half, 1), (S('3/2'),), log((1 + sqrt(z))/(1 - sqrt(z)))/(2*sqrt(z)))
    add((S.Half, S.Half), (S('3/2'),), asin(sqrt(z))/sqrt(z))
    add((S.Half - a, 1 - a), (S('3/2'),),
        ((1 + sqrt(z))**(2*a) - (1 - sqrt(z))**(2*a))/(4*a*sqrt(z)))

    addb((-a, S.Half - a), (S.Half,),
         Matrix([(1 + sqrt(z))**(2*a), (1 - sqrt(z))**(2*a)]),
         Matrix([[S.Half, S.Half]]),
         diag(a*sqrt(z)/(1 + sqrt(z)), -a*sqrt(z)/(1 - sqrt(z))))

    # This reduces to a lower order formula.
    #add((a + 1, 2*a), (a,), (1 + z)*(1 - z)**(-2*a - 1))


class Mod1(object):
    """
    Represent an expression 'mod 1'.

    Beware: __eq__ and the hash are NOT compatible. (by design)
    This means that m1 == m2 does not imply hash(m1) == hash(m2).
    Code that creates Mod1 objects (like compute_buckets below) should be
    careful only to produce one instance of Mod1 for each class.
    """
    # TODO this should be backported to any implementation of a Mod object
    #      (c/f issue 2490)

    def __new__(cls, r):
        if r.is_Rational and not r.free_symbols:
            return r - r.p//r.q
        res = object.__new__(cls)
        res.expr = r
        return res

    def __repr__(self):
        return str(self.expr) + ' % 1'

    def __eq__(self, other):
        from sympy import simplify
        if simplify(self.expr - other.expr).is_integer is True:
            return True
        return False

class IndexPair(object):
    """ Holds a pair of indices, and methods to compute their invariants. """

    def __init__(self, ap, bq):
        from sympy import expand, Tuple
        self.ap = Tuple(*[expand(x) for x in sympify(ap)])
        self.bq = Tuple(*[expand(x) for x in sympify(bq)])

    @property
    def sizes(self):
        return (len(self.ap), len(self.bq))

    def __str__(self):
        return 'IndexPair(%s, %s)' % (self.ap, self.bq)

    def compute_buckets(self, oabuckets=None, obbuckets=None):
        """
        Partition parameters `ap`, `bq` into buckets, that is return two dicts
        abuckets, bbuckets such that every key in [ab]buckets is a rational in
        range [0, 1) and the corresponding items are items of ap/bq congruent to
        the key mod 1.

        If oabuckets, obbuckets is specified, try to use the same Mod1 objects
        for parameters where possible.

        >>> from sympy.simplify.hyperexpand import IndexPair
        >>> from sympy import S
        >>> ap = (S(1)/2, S(1)/3, S(-1)/2, -2)
        >>> bq = (1, 2)
        >>> IndexPair(ap, bq).compute_buckets()
        ({0: (-2,), 1/3: (1/3,), 1/2: (1/2, -1/2)}, {0: (1, 2)})
        """
        # TODO this should probably be cached somewhere
        abuckets = {}
        bbuckets = {}

        oaparametric = []
        obparametric = []
        if oabuckets is not None:
            for parametric, buckets in [(oaparametric, oabuckets),
                                        (obparametric, obbuckets)]:
                parametric += filter(lambda x: isinstance(x, Mod1),
                                     buckets.keys())

        for params, bucket, oparametric in [(self.ap, abuckets, oaparametric),
                                            (self.bq, bbuckets, obparametric)]:
            parametric = []
            for p in params:
                if p == 0:
                    raise ValueError('parameters must not be zero')
                res = Mod1(p)
                if isinstance(res, Mod1):
                    parametric.append(p)
                    continue
                if res in bucket:
                    bucket[res] += (p,)
                else:
                    bucket[res] = (p,)
            while parametric:
                p0 = parametric[0]
                p0mod1 = Mod1(p0)
                if oparametric.count(p0mod1):
                    i = oparametric.index(p0mod1)
                    p0mod1 = oparametric.pop(i)
                bucket[p0mod1] = (p0,)
                pos = []
                for po in parametric[1:]:
                    if Mod1(po) == p0mod1:
                        bucket[p0mod1] += (po,)
                    else:
                        pos.append(po)
                parametric = pos

        return abuckets, bbuckets

    def build_invariants(self):
        """
        Compute the invariant vector of (`ap`, `bq`), that is:
            (gamma, ((s1, n1), ..., (sk, nk)), ((t1, m1), ..., (tr, mr)))
        where gamma is the number of integer a < 0,
              s1 < ... < sk
              nl is the number of parameters a_i congruent to sl mod 1
              t1 < ... < tr
              ml is the number of parameters b_i congruent to tl mod 1

        If the index pair contains parameters, then this is not truly an
        invariant, since the parameters cannot be sorted uniquely mod1.

        >>> from sympy.simplify.hyperexpand import IndexPair
        >>> from sympy import S
        >>> ap = (S(1)/2, S(1)/3, S(-1)/2, -2)
        >>> bq = (1, 2)

        Here gamma = 1,
             k = 3, s1 = 0, s2 = 1/3, s3 = 1/2
                    n1 = 1, n2 = 1,   n2 = 2
             r = 1, t1 = 0
                    m1 = 2:
        >>> IndexPair(ap, bq).build_invariants()
        (1, ((0, 1), (1/3, 1), (1/2, 2)), ((0, 2),))
        """
        abuckets, bbuckets = self.compute_buckets()

        gamma = 0
        if S(0) in abuckets:
            gamma = len(filter(lambda x: x < 0, abuckets[S(0)]))

        def tr(bucket):
            bucket = bucket.items()
            if not any(isinstance(x[0], Mod1) for x in bucket):
                bucket.sort(key=lambda x: x[0])
            bucket = tuple(map(lambda x: (x[0], len(x[1])), bucket))
            return bucket

        return (gamma, tr(abuckets), tr(bbuckets))

    def difficulty(self, ip):
        """ Estimate how many steps it takes to reach `ip` from self.
            Return -1 if impossible. """
        oabuckets, obbuckets = self.compute_buckets()
        abuckets, bbuckets = ip.compute_buckets(oabuckets, obbuckets)

        gt0 = lambda x: (x > 0) is True
        if S(0) in abuckets and (not S(0) in oabuckets or
             len(filter(gt0, abuckets[S(0)])) != len(filter(gt0, oabuckets[S(0)]))):
            return -1

        diff = 0
        for bucket, obucket in [(abuckets, oabuckets), (bbuckets, obbuckets)]:
            for mod in set(bucket.keys() + obucket.keys()):
                if (not mod in bucket) or (not mod in obucket) \
                   or len(bucket[mod]) != len(obucket[mod]):
                    return -1
                l1 = list(bucket[mod])
                l2 = list(obucket[mod])
                l1.sort()
                l2.sort()
                for i, j in zip(l1, l2):
                    diff += abs(i - j)

        return diff

# Dummy generator
x = Dummy('x')

class Formula(object):
    """
    This class represents hypergeometric formulae.

    Its data members are:
    - z, the argument
    - closed_form, the closed form expression
    - symbols, the free symbols (parameters) in the formula
    - indices, the parameters
    - B, C, M (see _compute_basis)
    - lcms, a dictionary which maps symbol -> lcm of denominators
    - isolation, a dictonary which maps symbol -> (num, coeff) pairs

    >>> from sympy.abc import a, b, z
    >>> from sympy.simplify.hyperexpand import Formula
    >>> f = Formula((a/2, a/3 + b, (1+a)/2), (a, b, (a+b)/7), z, None, [a, b])

    The lcm of all denominators of coefficients of a is 2*3*7
    >>> f.lcms[a]
    42

    for b it is just 7:
    >>> f.lcms[b]
    7

    We can isolate a in the (1+a)/2 term, with denominator 2:
    >>> f.isolation[a]
    (2, 2, 1)

    b is isolated in the b term, with coefficient one:
    >>> f.isolation[b]
    (4, 1, 1)
    """

    def _compute_basis(self, closed_form):
        """
        Compute a set of functions B=(f1, ..., fn), a nxn matrix M
        and a 1xn matrix C such that:
           closed_form = C B
           z d/dz B = M B.
        """
        from sympy.matrices import Matrix, eye, zeros

        afactors = map(lambda a: x + a, self.indices.ap)
        bfactors = map(lambda b: x + b - 1, self.indices.bq)
        expr = x*Mul(*bfactors) - self.z*Mul(*afactors)
        poly = Poly(expr, x)

        n = poly.degree() - 1
        b = [closed_form]
        for _ in xrange(n):
            b.append(self.z*b[-1].diff(self.z))

        self.B = Matrix(b)
        self.C = Matrix([[1] + [0]*n])

        m = eye(n)
        m = m.col_insert(0, zeros((n, 1)))
        l = poly.all_coeffs()[1:]
        l.reverse()
        self.M = m.row_insert(n, -Matrix([l])/poly.all_coeffs()[0])

    def __init__(self, ap, bq, z, res, symbols, B=None, C=None, M=None):
        ap = Tuple(*map(expand, sympify(ap)))
        bq = Tuple(*map(expand, sympify(bq)))
        z  = sympify(z)
        res = sympify(res)
        symbols = filter(lambda x: ap.has(x) or bq.has(x), sympify(symbols))

        self.z  = z
        self.symbols = symbols
        self.B = B
        self.C = C
        self.M = M

        params = list(ap) + list(bq)
        lcms = {}
        isolation = {}
        for a in symbols:
            from sympy import ilcm
            l = 1
            isolating = []
            others = list(symbols[:])
            others.remove(a)
            i = 0
            for p in params:
                if p.has(a):
                    c, m = None, None
                    if p.is_Add:
                        c, m = p.as_independent(a)[1].as_coeff_mul(a)
                    else:
                        c, m = p.as_coeff_mul(a)
                    if m != (a,) or not c.is_Rational:
                        raise NotImplementedError('?')
                    l = ilcm(l, c.q)

                    if not p.has(*others):
                        isolating.append((i, c.q, c.p))
                lcms[a] = l
                i += 1
            if len(isolating) == 0:
                raise NotImplementedError('parameter is not isolated')
            isolating.sort(key=lambda x:x[1])
            isolating.sort(key=lambda x:-x[2])
            isolation[a] = isolating[-1]

        self.lcms = lcms
        self.isolation = isolation

        self.indices = IndexPair(ap, bq)

        # TODO with symbolic parameters, it could be advantageous
        #      (for prettier answers) to compute a basis only *after*
        #      instantiation
        if res is not None:
            self._compute_basis(res)

    @property
    def closed_form(self):
        return (self.C*self.B)[0]

    def find_instantiations(self, ip):
        """
        Try to find instantiations of the free symbols that match
        `ip.ap`, `ip.bq`. Return the instantiated formulae as a list.
        Note that the returned instantiations need not actually match,
        or be valid!
        """
        ap = ip.ap
        bq = ip.bq
        if len(ap) != len(self.indices.ap) or len(bq) != len(self.indices.bq):
            raise TypeError('Cannot instantiate other number of parameters')

        from sympy import solve
        from itertools import permutations, product
        res = []
        our_params = list(self.indices.ap) + list(self.indices.bq)
        for na in permutations(ap):
            for nb in permutations(bq):
                all_params = list(na) + list(nb)
                repl = {}
                for a in self.symbols:
                    i, d, _ = self.isolation[a]
                    repl[a] = (solve(our_params[i] - all_params[i], a)[0], d)
                for change in product(*[(-1, 0, 1)]*len(self.symbols)):
                    rep = {}
                    for i, a in zip(change, repl.keys()):
                        rep[a] = repl[a][0] + i*repl[a][1]
                    res.append(Formula(self.indices.ap.subs(rep),
                                       self.indices.bq.subs(rep),
                                       self.z, None, [], self.B.subs(rep),
                                       self.C.subs(rep), self.M.subs(rep)))
                # if say a = -1/2, and there is 2*a in the formula, then
                # there will be a negative integer. But this origin is also
                # reachable from a = 1/2 ...
                # So throw this in as well.
                # The code is not as general as it could be, but good enough.
                if len(self.symbols) == 1:
                    a = self.symbols[0]
                    aval, d = repl[a]
                    if aval < 0 and d == 1:
                        from sympy import ceiling
                        aval -= ceiling(aval) - 1
                        res.append(Formula(self.indices.ap.subs(a, aval),
                                           self.indices.bq.subs(a, aval),
                                       self.z, None, [], self.B.subs(a, aval),
                                       self.C.subs(rep), self.M.subs(a, aval)))
        return res

    def is_suitable(self):
        """
        Decide if `self` is a suitable origin.

        >>> from sympy.simplify.hyperexpand import Formula
        >>> from sympy import S

        If ai - bq in Z and bq >= ai this is fine:
        >>> Formula((S(1)/2,), (S(3)/2,), None, None, []).is_suitable()
        True

        but ai = bq is not:
        >>> Formula((S(1)/2,), (S(1)/2,), None, None, []).is_suitable()
        False

        and ai > bq is not either:
        >>> Formula((S(1)/2,), (-S(1)/2,), None, None, []).is_suitable()
        False

        None of the bj can be a non-positive integer:
        >>> Formula((S(1)/2,), (0,), None, None, []).is_suitable()
        False
        >>> Formula((S(1)/2,), (-1, 1,), None, None, []).is_suitable()
        False

        None of the ai can be zero:
        >>> Formula((S(1)/2, 0), (1,), None, None, []).is_suitable()
        False


        More complicated examples:
        >>> Formula((S(1)/2, 1), (2, -S(2)/3), None, None, []).is_suitable()
        True
        >>> Formula((S(1)/2, 1), (2, -S(2)/3, S(3)/2), None, None, []).is_suitable()
        True
        """
        from sympy import oo, zoo
        if len(self.symbols) > 0:
            return None
        for a in self.indices.ap:
            for b in self.indices.bq:
                if (a-b).is_integer and not a < b:
                    return False
        for a in self.indices.ap:
            if a == 0:
                return False
        for b in self.indices.bq:
            if b <= 0 and b.q == 1:
                return False
        for e in [self.B, self.M, self.C]:
            if e is None:
                continue
            if e.has(S.NaN) or e.has(oo) or e.has(-oo) or e.has(zoo):
                return False
        return True


class FormulaCollection(object):
    """ A collection of formulae to use as origins. """

    def __init__(self):
            """ Doing this globally at module init time is a pain ... """
            self.symbolic_formulae = {}
            self.concrete_formulae = {}
            self.formulae = []

            add_formulae(self.formulae)

            # Now process the formulae into a helpful form.
            # These dicts are indexed by (p, q).

            for f in self.formulae:
                sizes = f.indices.sizes
                if len(f.symbols) > 0:
                    self.symbolic_formulae.setdefault(sizes, []).append(f)
                else:
                    inv = f.indices.build_invariants()
                    self.concrete_formulae.setdefault(sizes, {})[inv] = f

    def lookup_origin(self, ip):
        """
        Given the suitable parameters `ip.ap`, `ip.bq`, try to find an origin
        in our knowledge base.

        >>> from sympy.simplify.hyperexpand import FormulaCollection, IndexPair
        >>> f = FormulaCollection()
        >>> f.lookup_origin(IndexPair((), ())).closed_form
        exp(_z)
        >>> f.lookup_origin(IndexPair([1], ())).closed_form
        1/(-_z + 1)

        >>> from sympy import S
        >>> f.lookup_origin(IndexPair([S('1/4'), S('3/4 + 4')], [S.Half])).closed_form
        ((-_z + 1)**(1/2)/2 + 1/2)**(1/2)
        """
        inv = ip.build_invariants()
        sizes = ip.sizes
        if sizes in self.concrete_formulae and \
           inv in self.concrete_formulae[sizes]:
            return self.concrete_formulae[sizes][inv]

        # We don't have a concrete formula. Try to instantiate.
        if not sizes in self.symbolic_formulae:
            return None # Too bad...

        possible = []
        for f in self.symbolic_formulae[sizes]:
            l = f.find_instantiations(ip)
            for f2 in l:
                if not f2.is_suitable():
                    continue
                diff = f2.indices.difficulty(ip)
                if diff != -1:
                    possible.append((diff, f2))

        if not possible:
            # Give up.
            return None

        # find the nearest origin
        possible.sort(key=lambda x:x[0])
        return possible[0][1]


class Operator(object):
    """
    Base class for operators to be applied to our functions.

    These operators are differential operators. They are by convention
    expressed in the variable D = z*d/dz (although this base class does
    not actually care).
    Note that when the operator is applied to an object, we typically do
    *not* blindly differentiate but instead use a different representation
    of the z*d/dz operator (see make_derivative_operator).

    To subclass from this, define a __init__ method that initalises a
    self._poly variable. This variable stores a polynomial. By convention
    the generator is z*d/dz, and acts to the right of all coefficients.

    Thus this poly
        x**2 + 2*z*x + 1
    represents the differential operator
        (z*d/dz)**2 + 2*z**2*d/dz.

    This class is used only in the implementation of the hypergeometric
    function expansion algorithm.
    """

    def apply(self, obj, op):
        """
        Apply `self` to the object `obj`, where the generator is given by `op`.

        >>> from sympy.simplify.hyperexpand import Operator
        >>> from sympy.polys.polytools import Poly
        >>> from sympy.abc import x, y, z
        >>> op = Operator()
        >>> op._poly = Poly(x**2 + z*x + y, x)
        >>> op.apply(z**7, lambda f: f.diff(z))
        y*z**7 + 7*z**7 + 42*z**5
        """
        coeffs = self._poly.all_coeffs()
        coeffs.reverse()
        diffs  = [obj]
        for c in coeffs[1:]:
            diffs.append(op(diffs[-1]))
        r = coeffs[0]*diffs[0]
        for c, d in zip(coeffs[1:], diffs[1:]):
            r += c*d
        return r

class MultOperator(Operator):
    """ Simply multiply by a "constant" """

    def __init__(self, p):
        self._poly = Poly(p, x)

class ShiftA(Operator):
    """ Increment an upper index. """

    def __init__(self, ai):
        ai = sympify(ai)
        if ai == 0:
            raise ValueError('Cannot increment zero upper index.')
        self._poly = Poly(x/ai + 1, x)

    def __str__(self):
        return '<Increment upper %s.>' % (1/self._poly.all_coeffs()[0])

class ShiftB(Operator):
    """ Decrement a lower index. """

    def __init__(self, bi):
        bi = sympify(bi)
        if bi == 1:
            raise ValueError('Cannot decrement unit lower index.')
        self._poly = Poly(x/(bi - 1) + 1, x)

    def __str__(self):
        return '<Decrement lower %s.>' % (1/self._poly.all_coeffs()[0] + 1)

class UnShiftA(Operator):
    """ Decrement an upper index. """

    def __init__(self, ap, bq, i, z):
        """ Note: i counts from zero! """
        ap, bq, i = map(sympify, [ap, bq, i])

        self._ap = ap
        self._bq = bq
        self._i  = i

        ap = list(ap)
        bq = list(bq)
        ai = ap.pop(i) - 1

        if ai == 0:
            raise ValueError('Cannot decrement unit upper index.')

        m = Poly(z*ai, x)
        for a in ap:
            m *= Poly(x + a, x)
        #print m

        A = Dummy('A')
        D = Poly(ai*A - ai, A)
        n = 1*D
        for b in bq:
            n *= (D + b - 1)
        #print n

        b0 = -n.all_coeffs()[-1]
        if b0 == 0:
            raise ValueError('Cannot decrement upper index: ' \
                               'cancels with lower')
        #print b0

        n = Poly(Poly(n.all_coeffs()[:-1], A).as_expr().subs(A, x/ai + 1), x)

        self._poly = Poly((n-m)/b0, x)

    def __str__(self):
        return '<Decrement upper index #%s of %s, %s.>' % (self._i,
                                                        self._ap, self._bq)

class UnShiftB(Operator):
    """ Increment a lower index. """

    def __init__(self, ap, bq, i, z):
        """ Note: i counts from zero! """
        ap, bq, i = map(sympify, [ap, bq, i])

        self._ap = ap
        self._bq = bq
        self._i  = i

        ap = list(ap)
        bq = list(bq)
        bi = bq.pop(i) + 1

        if bi == 0:
            raise ValueError('Cannot increment -1 lower index.')

        m = Poly(x*(bi-1), x)
        for b in bq:
            m *= Poly(x + b - 1, x)
        #print m

        B = Dummy('B')
        D = Poly((bi-1)*B - bi + 1, B)
        n = Poly(z, B)
        for a in ap:
            n *= (D + a)
        #print n

        b0 = n.all_coeffs()[-1]
        #print b0
        if b0 == 0:
            raise ValueError('Cannot increment index: ' \
                               'cancels with upper')
        #print b0

        n = Poly(Poly(n.all_coeffs()[:-1], B).as_expr().subs(B, x/(bi-1) + 1), x)
        #print n

        self._poly = Poly((m-n)/b0, x)

    def __str__(self):
        return '<Increment lower index #%s of %s, %s.>' % (self._i,
                                                        self._ap, self._bq)

class ReduceOrder(Operator):
    """ Reduce Order by cancelling an upper and a lower index. """

    def __new__(cls, ai, bj):
        """ For convenience if reduction is not possible, return None. """
        ai = sympify(ai)
        bj = sympify(bj)
        n = ai - bj
        if n < 0 or not n.is_Integer:
            return None
        if bj.is_integer and bj <= 0 and bj + n >= 0:
            return None

        self = Operator.__new__(cls)

        p = S(1)
        for k in xrange(n):
            p *= (x + bj + k)/(bj + k)

        self._poly = Poly(p, x)
        self._a = ai
        self._b = bj

        return self

    def __str__(self):
        return '<Reduce order by cancelling upper %s with lower %s.>' % \
                  (self._a, self._b)

def reduce_order(ip):
    """
    Given the hypergeometric parameters `ip.ap`, `ip.bq`, find a sequence of operators
    to reduces order as much as possible.

    Return (nip, [operators]), where applying the operators to the
    hypergeometric function specified by nip.ap, nip.bq yields ap, bq.

    Examples:

    >>> from sympy.simplify.hyperexpand import reduce_order, IndexPair
    >>> reduce_order(IndexPair((1, 2), (3, 4)))
    (IndexPair((1, 2), (3, 4)), [])
    >>> reduce_order(IndexPair((1,), (1,)))
    (IndexPair((), ()), [<Reduce order by cancelling upper 1 with lower 1.>])
    >>> reduce_order(IndexPair((2, 4), (3, 3)))
    (IndexPair((2,), (3,)), [<Reduce order by cancelling upper 4 with lower 3.>])
    """
    ap = list(ip.ap)
    bq = list(ip.bq)

    nap = []
    # we will edit bq in place
    operators = []
    for a in ap:
        op = None
        for i in xrange(len(bq)):
            op = ReduceOrder(a, bq[i])
            if op is not None:
                bq.pop(i)
                break
        if op is None:
            nap.append(a)
        else:
            operators.append(op)

    return IndexPair(Tuple(*nap), Tuple(*bq)), operators

def make_derivative_operator(M, z):
    """ Create a derivative operator, to be passed to Operator.apply. """
    def doit(C):
        r = z*C.diff(z) + C*M
        r.simplify() # this is probably a good idea
        return r
    return doit

def apply_operators(obj, ops, op):
    """
    Apply the list of operators `ops` to object `obj`, substituting `op` for the
    generator.
    """
    res = obj
    for o in reversed(ops):
        res = o.apply(res, op)
    return res

def devise_plan(ip, nip, z):
    """
    Devise a plan (consisting of shift and un-shift operators) to be applied
    to the hypergeometric function (`nip.ap`, `nip.bq`) to yield
    (`ip.ap`, `ip.bq`).
    Returns a list of operators.

    >>> from sympy.simplify.hyperexpand import devise_plan, IndexPair
    >>> from sympy.abc import z

    Nothing to do:

    >>> devise_plan(IndexPair((1, 2), ()), IndexPair((1, 2), ()), z)
    []
    >>> devise_plan(IndexPair((), (1, 2)), IndexPair((), (1, 2)), z)
    []

    Very simple plans:

    >>> devise_plan(IndexPair((2,), ()), IndexPair((1,), ()), z)
    [<Increment upper 1.>]
    >>> devise_plan(IndexPair((), (2,)), IndexPair((), (1,)), z)
    [<Increment lower index #0 of [], [1].>]

    Several buckets:

    >>> from sympy import S
    >>> devise_plan(IndexPair((1, S.Half), ()), IndexPair((2, S('3/2')), ()), z)
    [<Decrement upper index #0 of [2, 1/2], [].>, <Decrement upper index #0 of [3/2, 2], [].>]

    A slightly more complicated plan:

    >>> devise_plan(IndexPair((1, 3), ()), IndexPair((2, 2), ()), z)
    [<Increment upper 2.>, <Decrement upper index #0 of [2, 2], [].>]

    Another more complicated plan: (note that the ap have to be shifted first!)

    >>> devise_plan(IndexPair((1, -1), (2,)), IndexPair((3, -2), (4,)), z)
    [<Decrement lower 3.>, <Decrement lower 4.>, <Decrement upper index #1 of [-1, 2], [4].>, <Decrement upper index #1 of [-1, 3], [4].>, <Increment upper -2.>]
    """
    abuckets, bbuckets = ip.compute_buckets()
    nabuckets, nbbuckets = nip.compute_buckets(abuckets, bbuckets)

    if len(abuckets.keys()) != len(nabuckets.keys()) or \
       len(bbuckets.keys()) != len(nbbuckets.keys()):
        raise ValueError('%s not reachable from %s' % (ip, nip))

    ops = []

    def do_shifts(fro, to, inc, dec):
        ops = []
        for i in xrange(len(fro)):
            if to[i] - fro[i] > 0:
                sh = inc
                ch = 1
            else:
                sh = dec
                ch = -1

            while to[i] != fro[i]:
                ops += [sh(fro, i)]
                fro[i] += ch

        return ops

    def do_shifts_a(nal, nbk, al, aother, bother):
        """ Shift us from (nal, nbk) to (al, nbk). """
        return do_shifts(nal, al, lambda p, i: ShiftA(p[i]),
                         lambda p, i: UnShiftA(p + aother, nbk + bother, i, z))

    def do_shifts_b(nal, nbk, bk, aother, bother):
        """ Shift us from (nal, nbk) to (nal, bk). """
        return do_shifts(nbk, bk,
                         lambda p, i: UnShiftB(nal + aother, p + bother, i, z),
                         lambda p, i: ShiftB(p[i]))

    for r in set(abuckets.keys() + bbuckets.keys()):
        al = ()
        nal = ()
        bk = ()
        nbk = ()
        if r in abuckets:
            al = abuckets[r]
            nal = nabuckets[r]
        if r in bbuckets:
            bk = bbuckets[r]
            nbk = nbbuckets[r]
        if len(al) != len(nal) or len(bk) != len(nbk):
            raise ValueError('%s not reachable from %s' % ((ap, bq), (nap, nbq)))

        al = sorted(list(al))
        nal = sorted(list(nal))
        bk = sorted(list(bk))
        nbk = sorted(list(nbk))

        def others(dic, key):
            l = []
            for k, value in dic.iteritems():
                if k != key:
                    l += list(dic[k])
            return l
        aother = others(nabuckets, r)
        bother = others(nbbuckets, r)

        if len(al) == 0:
            # there can be no complications, just shift the bs as we please
            ops += do_shifts_b([], nbk, bk, aother, bother)
        elif len(bk) == 0:
            # there can be no complications, just shift the as as we please
            ops += do_shifts_a(nal, [], al, aother, bother)
        else:
            namax = nal[-1]
            amax  = al[-1]

            if nbk[0] <= namax or bk[0] <= amax:
                raise ValueError('Non-suitable parameters.')

            if namax > amax:
                # we are going to shift down - first do the as, then the bs
                ops += do_shifts_a(nal, nbk, al, aother, bother)
                ops += do_shifts_b(al, nbk, bk, aother, bother)
            else:
                # we are going to shift up - first do the bs, then the as
                ops += do_shifts_b(nal, nbk, bk, aother, bother)
                ops += do_shifts_a(nal, bk, al, aother, bother)

        nabuckets[r] = al
        nbbuckets[r] = bk

    ops.reverse()
    return ops

def try_shifted_sum(ip, z):
    """ Try to recognise a hypergeometric sum that starts from k > 0. """
    from sympy.functions import rf, factorial
    abuckets, bbuckets = ip.compute_buckets()
    if not S(0) in abuckets or len(abuckets[S(0)]) != 1:
        return None
    r = abuckets[S(0)][0]
    if r <= 0:
        return None
    if not S(0) in bbuckets:
        return None
    l = list(bbuckets[S(0)])
    l.sort()
    k = l[0]
    if k <= 0:
        return None

    nap = list(ip.ap)
    nap.remove(r)
    nbq = list(ip.bq)
    nbq.remove(k)
    k -= 1
    nap = map(lambda x: x - k, nap)
    nbq = map(lambda x: x - k, nbq)

    ops = []
    for n in xrange(r - 1):
        ops.append(ShiftA(n + 1))
    ops.reverse()

    fac = factorial(k)/z**k
    for a in nap:
        fac /= rf(a, k)
    for b in nbq:
        fac *= rf(b, k)

    ops += [MultOperator(fac)]

    p = 0
    for n in xrange(k):
        m = z**n/factorial(n)
        for a in nap:
            m *= rf(a, n)
        for b in nbq:
            m /= rf(b, n)
        p += m

    return IndexPair(nap, nbq), ops, -p

collection = None
def _hyperexpand(ip, z):
    """ Try to find an expression for the hypergeometric function
        `ip.ap`, `ip.bq`. """
    from sympy.simplify import powdenest, simplify

    # TODO
    # The following would be possible:
    # 1) Partial simplification (i.e. return a simpler hypergeometric function,
    #    even if we cannot express it in terms of named special functions).
    # 2) PFD Duplication (see Kelly Roach's paper)
    # 3) If the coefficients are a rational function of n (numerator parameters
    #    k, a1, ..., an, denominator parameters a1+k1, a2+k2, ..., an+kn, where
    #    k, k1, ..., kn are integers) then result can be expressed using Lerch
    #    transcendent. Under certain conditions, this simplifies to polylogs
    #    or even zeta functions. C/f Kelly Roach's paper.

    global collection
    if collection is None:
        collection = FormulaCollection()

    # First reduce order as much as possible.
    nip, ops = reduce_order(ip)

    # Our dummy variable
    z0 = Dummy('z0')

    # Try to recognise a shifted sum.
    p = S(0)
    res = try_shifted_sum(nip, z0)
    if res != None:
        nip, nops, p = res
        ops += nops

    # apply the plan for poly
    p = apply_operators(p, ops, lambda f: z0*f.diff(z0))
    p = simplify(p).subs(z0, z)

    # Now try to find a formula
    f = collection.lookup_origin(nip)

    if f is None:
        # There is nothing we can do.
        return None

    # We need to find the operators that convert f into (nap, nbq).
    ops += devise_plan(nip, f.indices, z0)

    # Now carry out the plan.
    C = apply_operators(f.C.subs(f.z, z0), ops,
                        make_derivative_operator(f.M.subs(f.z, z0), z0))

    C.simplify() # is this a good idea?
    r = C*f.B.subs(f.z, z0)
    r = r[0].subs(z0, z) + p

    # This will simpliy things like sqrt(-z**2) to i*z.
    # It would be wrong under certain choices of branch, but all results we
    # return are under an "implicit suitable choice of branch" anyway.
    return powdenest(r, force=True)

def hyperexpand(f):
    """
    Expand hypergeometric functions.

    Examples:

    >>> from sympy.simplify.hyperexpand import hyperexpand
    >>> from sympy.functions import hyper
    >>> from sympy.abc import z
    >>> hyperexpand(hyper([], [], z))
    exp(z)

    Non-hyperegeometric parts of the expression and hypergeometric expressions
    that are not recognised are left unchanged:

    >>> hyperexpand(1 + hyper([1, 1, 1], [], z))
    1 + hyper((1, 1, 1), (), z)
    """
    from sympy.functions import hyper
    f = sympify(f)
    def do_replace(ap, bq, z):
        r = _hyperexpand(IndexPair(ap, bq), z)
        if r is None:
            return hyper(ap, bq, z)
        else:
            return r
    return f.replace(hyper, do_replace)

from sympy.polys.polytools import Poly
