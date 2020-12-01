# coding: utf-8
# Copyright (c) Pymatgen Development Team.
# Distributed under the terms of the MIT License.

import copy
import numpy as np
from typing import Any, Dict, List, Optional, Tuple
import networkx as nx
from monty.json import MSONable
from monty.dev import deprecated
from pymatgen.core.structure import Molecule
from pymatgen.analysis.fragmenter import metal_edge_extender
from pymatgen.analysis.graphs import MoleculeGraph, MolGraphSplitError
from pymatgen.analysis.local_env import OpenBabelNN

__author__ = "Sam Blau, Mingjian Wen"
__copyright__ = "Copyright 2019, The Materials Project"
__version__ = "0.1"
__email__ = "samblau1@gmail.com"
__status__ = "Alpha"
__date__ = "Aug 1, 2019"


class MoleculeEntry(MSONable):
    """
    A molecule entry class to provide easy access to Molecule properties.

    Args:
        molecule: Molecule of interest.
        energy: Electronic energy of the molecule in Hartree.
        correction: A correction to be applied to the energy.
            This is used to modify the energy for certain analyses.
            Defaults to 0.0.
        enthalpy: Enthalpy of the molecule (kcal/mol). Defaults to None.
        entropy: Entropy of the molecule (cal/mol.K). Defaults to None.
        parameters: An optional dict of parameters associated with
            the molecule. Defaults to None.
        entry_id: An optional id to uniquely identify the entry.
        attribute: Optional attribute of the entry. This can be used to
            specify that the entry is a newly found compound, or to specify
            a particular label for the entry, or else ... Used for further
            analysis and plotting purposes. An attribute can be anything
            but must be MSONable.
        mol_doc: MongoDB document that contains information of the molecule.
        mol_graph: MoleculeGraph of the molecule.
    """

    # TODO (mjwen) remove mol_doc from __init__ and self.mol_doc (large dict).
    #  `from_molecule_document` provides the functionality for initialization.
    def __init__(
        self,
        molecule: Molecule,
        energy: float,
        correction: float = 0.0,
        enthalpy: Optional[float] = None,
        entropy: Optional[float] = None,
        parameters: Optional[Dict] = None,
        entry_id: Optional[Any] = None,
        attribute=None,
        mol_doc: Optional[Dict] = None,
        mol_graph: Optional[MoleculeGraph] = None,
        dummy: Optional[bool] = False,
    ):
        self.dummy = dummy
        self.uncorrected_energy = energy
        self.correction = correction
        self.enthalpy = enthalpy
        self.entropy = entropy
        self.parameters = parameters if parameters else {}
        self.entry_id = entry_id
        self.attribute = attribute
        self.mol_doc = mol_doc if mol_doc else {}
        self.mol_graph = mol_graph

        if self.mol_doc != {}:

            self.enthalpy = self.mol_doc["enthalpy_kcal/mol"]
            self.entropy = self.mol_doc["entropy_cal/molK"]
            self.entry_id = self.mol_doc["task_id"]
            if "mol_graph" in self.mol_doc:
                if isinstance(self.mol_doc["mol_graph"], MoleculeGraph):
                    self.mol_graph = self.mol_doc["mol_graph"]
                else:
                    self.mol_graph = MoleculeGraph.from_dict(self.mol_doc["mol_graph"])
            else:
                mol_graph = MoleculeGraph.with_local_env_strategy(molecule, OpenBabelNN())
                self.mol_graph = metal_edge_extender(mol_graph)
        else:
            if self.mol_graph is None:
                mol_graph = MoleculeGraph.with_local_env_strategy(molecule, OpenBabelNN())
                self.mol_graph = metal_edge_extender(mol_graph)

    def zip_dict(self):
        return {
            "enthalpy": self.enthalpy,
            "entropy": self.entropy,
            "energy": self.energy,
            "entry_id": self.entry_id,
            "charge": self.charge,
            "parameters": self.parameters,
        }

    @classmethod
    def from_molecule_document(
        cls,
        mol_doc: Dict,
        correction: float = 0.0,
        parameters: Optional[Dict] = None,
        attribute=None,
    ):
        """
        Initialize a MoleculeEntry from a molecule document.

        Args:
            mol_doc: MongoDB molecule document (nested dictionary) that contains the
                molecule information.
            correction: A correction to be applied to the energy. This is used to modify
                the energy for certain analyses. Defaults to 0.0.
            parameters: An optional dict of parameters associated with
                the molecule. Defaults to None.
            attribute: Optional attribute of the entry. This can be used to
                specify that the entry is a newly found compound, or to specify
                a particular label for the entry, or else ... Used for further
                analysis and plotting purposes. An attribute can be anything
                but must be MSONable.
        """
        try:
            if isinstance(mol_doc["molecule"], Molecule):
                molecule = mol_doc["molecule"]
            else:
                molecule = Molecule.from_dict(mol_doc["molecule"])
            energy = mol_doc["energy_Ha"]
            enthalpy = mol_doc["enthalpy_kcal/mol"]
            entropy = mol_doc["entropy_cal/molK"]
            entry_id = mol_doc["task_id"]
        except KeyError as e:
            raise MoleculeEntryError(
                "Unable to construct molecule entry from molecule document; missing "
                f"attribute {e} in `mol_doc`."
            )

        if "mol_graph" in mol_doc:
            if isinstance(mol_doc["mol_graph"], MoleculeGraph):
                mol_graph = mol_doc["mol_graph"]
            else:
                mol_graph = MoleculeGraph.from_dict(mol_doc["mol_graph"])
        else:
            mol_graph = MoleculeGraph.with_local_env_strategy(molecule, OpenBabelNN())
            mol_graph = metal_edge_extender(mol_graph)

        return cls(
            molecule=molecule,
            energy=energy,
            correction=correction,
            enthalpy=enthalpy,
            entropy=entropy,
            parameters=parameters,
            entry_id=entry_id,
            attribute=attribute,
            mol_graph=mol_graph,
        )

    @property
    def molecule(self):
        return self.mol_graph.molecule

    @property
    def graph(self) -> nx.MultiDiGraph:
        return self.mol_graph.graph

    @property
    def energy(self) -> float:
        return self.uncorrected_energy + self.correction

    @property
    def formula(self) -> str:
        return self.mol_graph.molecule.composition.alphabetical_formula

    @property
    def charge(self) -> float:
        return self.mol_graph.molecule.charge

    @property
    def species(self) -> List[str]:
        return [str(s) for s in self.mol_graph.molecule.species]

    @property
    def num_atoms(self) -> int:
        return len(self.mol_graph.molecule)

    @property
    @deprecated(message="`edges` is replaced by `bonds`. This will be removed shortly.")
    def edges(self) -> List[Tuple[int, int]]:
        return self.bonds

    @property
    def bonds(self) -> List[Tuple[int, int]]:
        return [tuple(sorted(e)) for e in self.graph.edges()]

    @property
    @deprecated(message="`Nbonds` is replaced by `num_bonds`. This will be removed shortly.")
    def Nbonds(self) -> int:
        return self.num_bonds

    @property
    def num_bonds(self) -> int:
        return len(self.bonds)

    @property
    def coords(self) -> np.ndarray:
        return self.mol_graph.molecule.cart_coords

    @deprecated(
        message="`free_energy(temp=<float>)` is replaced by "
        "get_free_energy(temperature=<float>)`. This will be removed shortly."
    )
    def free_energy(self, temp=298.15) -> float:
        return self.get_free_energy(temp)

    def get_free_energy(self, temp: float = 298.15) -> float:
        if self.enthalpy is not None and self.entropy is not None:
            return (
                self.energy * 27.21139
                + 0.0433641 * self.enthalpy
                - temp * self.entropy * 0.0000433641
            )
        else:
            return None

    def get_fragments(self) -> Dict[Tuple[int, int], List[MoleculeGraph]]:
        """
        Get the fragments of the molecule by breaking all its bonds.

        Returns:
            Fragments dict {(atom1, atom2): [fragments]}, where
                the key `(atom1, atom2)` specifies the broken bond indexed by the two
                atoms forming the bond, and the value `[fragments]` is a list of
                fragments obtained by breaking the bond. This list can have either one
                element (ring-opening A->B) or two elements (not ring-opening A->B+C).
                The dictionary is empty if the molecule has no bonds (e.g. Li+).
        """

        fragments = {}
        for edge in self.bonds:
            try:
                frags = self.mol_graph.split_molecule_subgraphs(
                    [edge], allow_reverse=True, alterations=None
                )
                fragments[edge] = frags

            except MolGraphSplitError:
                # cannot split (ring-opening editing)
                frag = copy.deepcopy(self.mol_graph)
                idx1, idx2 = edge
                frag.break_edge(idx1, idx2, allow_reverse=True)
                fragments[edge] = [frag]

        return fragments

    def get_isomorphic_bonds(
        self, fragments: Optional[Dict[Tuple[int, int], List[MoleculeGraph]]] = None
    ) -> List[List[Tuple[int, int]]]:
        """
        Find isomorphic bonds in the molecule.

        Isomorphic bonds are defined as bonds that when breaking them separately,
        the same fragments (in terms of graph connectivity) are obtained.

        For example, for molecule:

             b0      b1
        H(1)----C(0)----H(2)
            b2 /   | b3
            O(3)---O(4)
                b4

        (notation: number after b is bond index, number in `()` is atom index)

        bond 0 is isomorphic to bond 1, and bond 2 is isomorphic to bond 3.

        Args:
            fragments: a dictionary of fragments obtained by breaking all bonds in the
                molecule, can be obtained by `self.get_fragments()`. If `None`,
                will generate the fragments automatically.

        Returns:
            Isomorphic bonds specified by atom indexes: [[(atom1, atom2)]].
            Each inner list contains bonds (each bond is specified by the indexes of the
            atoms forming the bond `(atom1, atom2)`) that are isomorphic to each other.
            Note, bond not isomorphic to any other bond is included as a group by itself.
            For example, for the above shown molecule, this function returns:
            [[(0,1), (0,2)], [(0,3), (0,4)], [(3,4)]]
        """

        fragments = self.get_fragments() if fragments is None else fragments

        iso_bonds = []

        for current_bond, current_frags in fragments.items():
            for group in iso_bonds:

                # compare to the first element in a group to determine whether they are
                # isomorphic to each other
                existing_bond = group[0]
                exsiting_frags = fragments[existing_bond]

                # one fragments (ring-opening like fragments)
                if len(current_frags) == len(exsiting_frags) == 1:
                    if current_frags[0].isomorphic_to(exsiting_frags[0]):
                        group.append(current_bond)
                        break

                # two fragments
                elif len(current_frags) == len(exsiting_frags) == 2:
                    if (
                        current_frags[0].isomorphic_to(exsiting_frags[0])
                        and current_frags[1].isomorphic_to(exsiting_frags[1])
                    ) or (
                        current_frags[0].isomorphic_to(exsiting_frags[1])
                        and current_frags[1].isomorphic_to(exsiting_frags[0])
                    ):
                        group.append(current_bond)
                        break

            # current_bond not in any group, create a new group
            else:
                iso_bonds.append([current_bond])

        return iso_bonds

    def __repr__(self):
        output = [
            "MoleculeEntry {} - {} - E{} - C{}".format(
                self.entry_id, self.formula, self.Nbonds, self.charge
            ),
            "Energy = {:.4f} Hartree".format(self.uncorrected_energy),
            "Correction = {:.4f} Hartree".format(self.correction),
            "Enthalpy = {:.4f} kcal/mol".format(self.enthalpy),
            "Entropy = {:.4f} cal/mol.K".format(self.entropy),
            "Free Energy (298.15 K) = {:.4f} eV".format(self.get_free_energy()),
            "Parameters:",
        ]
        for k, v in self.parameters.items():
            output.append("{} = {}".format(k, v))
        return "\n".join(output)

    def __str__(self):
        return self.__repr__()


class MoleculeEntryError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message
