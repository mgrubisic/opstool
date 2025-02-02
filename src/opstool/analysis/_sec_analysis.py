import matplotlib.pyplot as plt
import numpy as np
import openseespy.opensees as ops

from ._smart_analyze import SmartAnalyze


class MomentCurvature:
    """Moment-Curvature Analysis for Fiber Section in OpenSeesPy.

    Parameters
    ----------
    sec_tag : int,
        The previously defined section Tag.
    axial_force : float, optional
        Axial load, compression is negative, by default 0
    """

    def __init__(self, sec_tag: int, axial_force: float = 0) -> None:
        self.P = axial_force
        self.sec_tag = sec_tag
        self.phi, self.M, self.FiberData = None, None, None

    def analyze(
        self,
        axis: str = "y",
        max_phi: float = 1.0,
        incr_phi: float = 1e-4,
        post_peak_ratio: float = 0.8,
        smart_analyze: bool = True,
    ):
        """Performing Moment-Curvature Analysis.

        Parameters
        ----------
        axis : str, optional, "y" or "z"
            The axis of the section to be analyzed, by default "y".
        max_phi : float, optional
            The maximum curvature to analyze, by default 1.0.
        incr_phi : float, optional
            Curvature analysis increment, by default 1e-4.
        post_peak_ratio : float, optional
            A ratio of the moment intensity after the peak used to stop the analysis., by default 0.7,
            i.e. a 30% drop after peak.
        smart_analyze : bool, optional
            Whether to use smart analysis options, by default True.

        .. note::
            The termination of the analysis depends on whichever reaches `max_phi` or `post_peak_ratio` first.
        """
        self.phi, self.M, self.FiberData = _analyze(
            sec_tag=self.sec_tag,
            P=self.P,
            axis=axis,
            max_phi=max_phi,
            incr_phi=incr_phi,
            stop_ratio=post_peak_ratio,
            smart_analyze=smart_analyze,
        )

    def plot_M_phi(self):
        """Plot the moment-curvature relationship."""
        _, ax = plt.subplots(1, 1, figsize=(10, 10 * 0.618))
        ax.plot(self.phi, self.M, lw=3, c="blue")
        ax.set_title(
            "$M-\\phi$",
            fontsize=28,
        )
        ax.set_xlabel("$\phi$", fontsize=25)
        ax.set_ylabel("$M$", fontsize=25)
        plt.xticks(fontsize=15)
        plt.yticks(fontsize=15)
        ax.spines["bottom"].set_linewidth(1.2)
        ax.spines["left"].set_linewidth(1.2)
        ax.spines["right"].set_linewidth(1.2)
        ax.spines["top"].set_linewidth(1.2)
        plt.gcf().subplots_adjust(bottom=0.15)
        plt.show()

    def plot_fiber_responses(self):
        """Plot the stress-strain histories for all fibers of each material."""
        fiber_data = self.FiberData
        matTags = np.unique(fiber_data[-1][:, 3])

        _, axs = plt.subplots(len(matTags), 1, figsize=(8, 3 * len(matTags)))
        for mat, ax in zip(matTags, axs):
            idxs = np.argwhere(np.abs(fiber_data[-1][:, 3] - mat) < 1e-6)
            strain = fiber_data[:, idxs, -1]
            stress = fiber_data[:, idxs, -2]
            for i in range(len(idxs)):
                ax.plot(
                    strain[:, i, :],
                    stress[:, i, :],
                    lw=1,
                )
            ax.set_title(f"matTag = {mat:.0f}", fontsize=15)
            ax.tick_params(labelsize=12)
            ax.set_ylabel("stress", fontsize=16)
        ax.set_xlabel("strain", fontsize=16)
        plt.subplots_adjust(wspace=0.02, hspace=0.4)
        plt.tight_layout()
        plt.show()

    def get_phi(self):
        """Get the curvature array.

        Returns
        -------
        1D array-like
            Curvature array.
        """
        return self.phi

    def get_curvature(self):
        """Get the curvature array.

        Returns
        -------
        1D array-like
            Curvature array.
        """
        return self.get_phi()

    def get_M(self):
        """Get the moment array.

        Returns
        -------
        1D array-like
            Moment array.
        """
        return self.M

    def get_moment(self):
        """Get the moment array.

        Returns
        -------
        1D array-like
            Moment array.
        """
        return self.get_M()

    def get_M_phi(self):
        """Get the moment and curvature array.

        Returns
        -------
        (1D array-like, 1D array-like)
            (Curvature array, Moment array)
        """
        return self.phi, self.M

    def get_fiber_data(self):
        """All fiber data.

        Returns
        -------
        Shape-(n,m,6) Array.
            n is the length of moment and curvature array, m is the fiber number,
            6 contain ("yCoord", "zCoord", "area", 'mat', "stress", "strain")
        """
        return self.FiberData

    def get_limit_state(
        self, matTag: int = 1, threshold: float = 0, use_peak_drop20: bool = False
    ):
        """Get the curvature and moment corresponding to a certain limit state.

        Parameters
        ----------
        matTag : int, optional
            The OpenSeesPy material Tag used to determine the limit state., by default 1
        threshold : float, optional
            The strain threshold used to determine the limit state by material `matTag`, by default 0
        use_peak_drop20 : bool, optional
            If True, A 20% drop from the peak value of the moment will be used as the limit state,
            and `matTag` and `threshold` are not needed, by default False.

        Returns
        -------
        (float, float)
            (Limit Curvature, Limit Moment)
        """
        phi = self.phi
        M = self.M
        fiber_data = self.FiberData
        if use_peak_drop20:
            idx = np.argmax(M)
            au = np.argwhere(M[idx:] <= np.max(M) * 0.80)
            if au.size == 0:
                raise RuntimeError(
                    "Peak strength does not drop 20%, please increase target ductility ratio!"
                )
            else:
                bu = np.min(au) + idx - 1
        else:
            idxu = np.argwhere(np.abs(fiber_data[-1][:, 3] - matTag) < 1e-6)
            eu = threshold
            if eu >= 0:
                strain = np.array([np.max(data[idxu, -1]) for data in fiber_data])
                au = np.argwhere(strain >= eu)
            else:
                strain = np.array([np.min(data[idxu, -1]) for data in fiber_data])
                au = np.argwhere(strain < eu)
            if len(au) == 0:
                raise RuntimeError(
                    "The ultimate strain is not reached, please increase target ductility ratio!"
                )
            else:
                bu = np.min(au)
        Phi_u = phi[bu]
        M_u = M[bu]
        return Phi_u, M_u

    def bilinearize(self, phiy: float, My: float, phiu: float, plot: bool = False):
        """Bilinear Approximation of Moment-Curvature Relation.

        Parameters
        ----------
        phiy : float
            The initial yield curvature.
        My : float
            The initial yield moment.
        phiu : float
            The limit curvature.
        plot : bool, optional
            If True, plot the bilinear approximation, by default False.

        Returns
        -------
        (float, float)
            (Equivalent Curvature, Equivalent Moment)
        """

        phi = self.phi
        M = self.M
        bu = np.argmin(np.abs(phiu - phi))
        Q = np.trapz(M[: bu + 1], phi[: bu + 1])
        k = My / phiy
        Phi_eq = (k * phiu - np.sqrt((k * phiu) ** 2 - 2 * k * Q)) / k
        M_eq = k * Phi_eq

        M_new = np.insert(M[0 : bu + 1], 0, 0, axis=None)
        Phi_new = np.insert(phi[0 : bu + 1], 0, 0, axis=None)

        if plot:
            _, ax = plt.subplots(1, 1, figsize=(10, 10 * 0.618))
            ax.plot(Phi_new, M_new, lw=1.5, c="#2529d8")
            ax.plot([0, phiy, Phi_eq, phiu], [0, My, M_eq, M_eq], lw=1.5, c="#de0f17")
            ax.plot(
                phiy,
                My,
                "o",
                ms=12,
                mec="black",
                mfc="#0099e5",
                label="Initial Yield ($\phi_y$,$M_y$)",
            )
            ax.plot(
                Phi_eq,
                M_eq,
                "*",
                ms=15,
                mec="black",
                mfc="#ff4c4c",
                label="Equivalent Yield ($\phi_{{eq}}$,$M_{{eq}}$)",
            )
            maxy = np.max(ax.get_yticks())
            ax.vlines(phiu, 0, maxy, colors="#34bf49", linestyles="dashed", lw=0.75)
            txt = (
                f"$\phi_y$={phiy:.3E}, $M_y$={My:.3E}\n"
                f"$\phi_{{eq}}$={Phi_eq:.3E}, $M_{{eq}}$={M_eq:.3E}\n"
                f"$\phi_{{u}}$={phiu:.3E}, $M_{{u}}$={M[bu]:.3E}"
            )
            ax.text(
                0.5,
                0.4,
                txt,
                fontsize=15,
                ha="center",
                va="bottom",
                transform=ax.transAxes,
            )
            ax.set_title(
                "Moment-Curvature",
                fontsize=22,
            )
            ax.set_xlabel("$\phi$", fontsize=20)
            ax.set_ylabel("$M$", fontsize=20)
            plt.xticks(fontsize=15)
            plt.yticks(fontsize=15)
            # ax.set_xlim(0, np.max(ax.get_xticks()))
            ax.set_ylim(0, maxy)
            ax.spines["bottom"].set_linewidth(1.2)
            ax.spines["left"].set_linewidth(1.2)
            ax.spines["right"].set_linewidth(1.2)
            ax.spines["top"].set_linewidth(1.2)
            ax.legend(loc="lower center", fontsize=15)
            plt.gcf().subplots_adjust(bottom=0.15)
            plt.show()
        return Phi_eq, M_eq


def _create_model(sec_tag):
    ops.model("basic", "-ndm", 3, "-ndf", 6)
    ops.node(1, 0.0, 0.0, 0.0)
    ops.node(2, 0.0, 0.0, 0.0)
    ops.fix(1, 1, 1, 1, 1, 1, 1)
    ops.fix(2, 0, 1, 1, 1, 0, 0)
    ops.element("zeroLengthSection", 1, 1, 2, sec_tag)


def _create_axial_resp(p):
    ops.timeSeries("Constant", 1)
    ops.pattern("Plain", 1, 1)
    ops.load(2, p, 0, 0, 0, 0, 0)  # nd  FX,  FY, Fz, MX, MY, MZ
    ops.wipeAnalysis()
    ops.system("SparseGeneral", "-piv")
    ops.constraints("Plain")
    ops.numberer("Plain")
    ops.test("NormDispIncr", 1.0e-12, 10, 3)
    ops.algorithm("Newton")
    ops.integrator("LoadControl", 1 / 10)
    ops.analysis("Static")
    ops.analyze(10)
    ops.loadConst("-time", 0.0)


def _analyze(
    sec_tag, P=0, axis="y", max_phi=1, incr_phi=1e-5, stop_ratio=0.7, smart_analyze=True
):
    _create_model(sec_tag=sec_tag)
    if P != 0:
        _create_axial_resp(P)
    ops.timeSeries("Linear", 2)
    ops.pattern("Plain", 2, 2)
    if axis.lower() == "y":
        dof = 5
        ops.load(2, 0, 0, 0, 0, 1, 0)
    elif axis.lower() == "z":
        dof = 6
        ops.load(2, 0, 0, 0, 0, 0, 1)
    else:
        raise ValueError("Only supported axis = y or z!")
    M = [0]
    PHI = [0]
    FIBER_RESPONSES = [0]
    if smart_analyze:
        protocol = [max_phi]
        userControl = {
            "analysis": "Static",
            "testType": "NormDispIncr",
            "testTol": 1.0e-8,
            "tryAlterAlgoTypes": True,
            "algoTypes": [10, 40, 30, 20],
            "relaxation": 0.5,
            "minStep": 1.0e-12,
            "printPer": 10000000000,
            "debugMode": False,
        }
        analysis = SmartAnalyze(analysis_type="Static", **userControl)
        segs = analysis.static_split(protocol, maxStep=incr_phi)
        ii = 0
        while True:
            seg = segs[ii]
            ii += 1
            analysis.StaticAnalyze(2, dof, seg)
            curr_M = ops.getLoadFactor(2)
            curr_Phi = ops.nodeDisp(2, dof)
            cond1 = np.abs(curr_M) < np.max(np.abs(M)) * (stop_ratio - 0.02)
            cond2 = np.abs(curr_Phi) > max_phi
            if cond1 or cond2:
                break
            PHI.append(ops.nodeDisp(2, dof))
            M.append(curr_M)
            FIBER_RESPONSES.append(_get_fiber_sec_data(ele_tag=1))

    else:
        ops.integrator("DisplacementControl", 2, dof, incr_phi)
        while True:
            ops.analyze(1)
            curr_M = ops.getLoadFactor(2)
            curr_Phi = ops.nodeDisp(2, dof)
            cond1 = np.abs(curr_M) < np.max(np.abs(M)) * (stop_ratio - 0.02)
            cond2 = np.abs(curr_Phi) > max_phi
            if cond1 or cond2:
                break
            PHI.append(ops.nodeDisp(2, dof))
            M.append(curr_M)
            FIBER_RESPONSES.append(_get_fiber_sec_data(ele_tag=1))
    FIBER_RESPONSES[0] = FIBER_RESPONSES[1] * 0
    return np.abs(PHI), np.abs(M), np.array(FIBER_RESPONSES)


def _get_fiber_sec_data(ele_tag: int):
    fiber_data = ops.eleResponse(ele_tag, "section", "fiberData2")
    # From column 1 to 6: "yCoord", "zCoord", "area", 'mat', "stress", "strain"
    fiber_data = np.array(fiber_data).reshape((-1, 6))
    return fiber_data
