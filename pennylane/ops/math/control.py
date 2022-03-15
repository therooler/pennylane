# Copyright 2018-2022 Xanadu Quantum Technologies Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# pylint: disable=too-many-arguments

from multimethod import multimethod
import warnings

import pennylane as qml
from pennylane.operation import Operator, AnyWires
from pennylane.wires import Wires
from pennylane import numpy as np
from ..qubit import PauliX, PauliY, SWAP, PhaseShift, RX, RY, RZ, Rot

class NoDecompositionShortcut(Exception):
    """decomposition undefined."""

@multimethod
def c1_decomp(op: Operator):
    raise NoDecompositionShortcut


@multimethod
def c1_decomp(op: PauliY, control):
    return [qml.CRY(np.pi, wires=control+op.wires), qml.S(wires=control)]


@multimethod
def c1_decomp(op: SWAP, control):
    return [
            qml.Toffoli(wires=[control, op.wires[1], op.wires[0]]),
            qml.Toffoli(wires=[control, op.wires[0], op.wires[1]]),
            qml.Toffoli(wires=[control, op.wires[1], op.wires[0]]),
    ]


@multimethod
def c1_decomp(op: PhaseShift, control):
    phi = op.data[0]
    return [
            qml.PhaseShift(phi / 2, wires=control),
            qml.CNOT(wires=control+op.wires),
            qml.PhaseShift(-phi / 2, wires=op.wires),
            qml.CNOT(wires=control+op.wires),
            qml.PhaseShift(phi / 2, wires=op.wires),
        ]


@multimethod
def c1_decomp(op: RX, control):
    phi = op.data[0]
    return [
            qml.RZ(np.pi / 2, wires=op.wires),
            qml.RY(phi / 2, wires=op.wires),
            qml.CNOT(wires=control+op.wires),
            qml.RY(-phi / 2, wires=op.wires),
            qml.CNOT(wires=control+op.wires),
            qml.RZ(-np.pi / 2, wires=op.wires),
        ]


@multimethod
def c1_decomp(op: RY, control):
    phi = op.data[0]
    return [
            qml.RY(phi / 2, wires=op.wires),
            qml.CNOT(wires=control+op.wires),
            qml.RY(-phi / 2, wires=op.wires),
            qml.CNOT(wires=control+op.wires),
        ]


@multimethod
def c1_decomp(op: RZ, control):
    phi = op.data[0]
    return [
            qml.PhaseShift(phi / 2, wires=op.wires),
            qml.CNOT(wires=control+op.wires),
            qml.PhaseShift(-phi / 2, wires=op.wires),
            qml.CNOT(wires=control+op.wires),
        ]


@multimethod
def c1_decomp(op: Rot):
    phi, theta, omega = op.data
    wires = op.wires
    return [
            qml.RZ((phi - omega) / 2, wires=wires[1]),
            qml.CNOT(wires=wires),
            qml.RZ(-(phi + omega) / 2, wires=wires[1]),
            qml.RY(-theta / 2, wires=wires[1]),
            qml.CNOT(wires=wires),
            qml.RY(theta / 2, wires=wires[1]),
            qml.RZ(omega, wires=wires[1]),
        ]

def multicx_decomposition(control_wires, target_wire, work_wires):
    num_work_wires_needed = len(control_wires) - 2
    if len(work_wires) < num_work_wires_needed:
        tot_wires = len(control_wires) + 2
        partition = int(qml.numpy.ceil(tot_wires / 2))

        first_part = control_wires[:partition]
        second_part = control_wires[partition:]

        gates = [
            Controlled(qml.PauliX(work_wires[0]),
                control_wires=first_part,
                work_wires=second_part + target_wire,
            ),
            Controlled(qml.PauliX(target_wire),
                control_wires=second_part + work_wires[0:1],
                work_wires=first_part,
            ),
            Controlled(qml.PauliX(work_wires[0]),
                control_wires=first_part,
                work_wires=second_part + target_wire,
            ),
            Controlled(qml.PauliX(target_wire),
                control_wires=second_part + work_wires[0:1],
                work_wires=first_part,
            ),
        ]
        return gates
    # decomposition with many wires
    work_wires = work_wires[:num_work_wires_needed]

    work_wires_reversed = list(reversed(work_wires))
    control_wires_reversed = list(reversed(control_wires))

    gates = []

    for i in range(len(work_wires)):
        ctrl1 = control_wires_reversed[i]
        ctrl2 = work_wires_reversed[i]
        t = target_wire if i == 0 else work_wires_reversed[i - 1]
        gates.append(qml.Toffoli(wires=[ctrl1, ctrl2, t]))

    gates.append(qml.Toffoli(wires=[*control_wires[:2], work_wires[0]]))

    for i in reversed(range(len(work_wires))):
        ctrl1 = control_wires_reversed[i]
        ctrl2 = work_wires_reversed[i]
        t = target_wire if i == 0 else work_wires_reversed[i - 1]
        gates.append(qml.Toffoli(wires=[ctrl1, ctrl2, t]))

    for i in range(len(work_wires) - 1):
        ctrl1 = control_wires_reversed[i + 1]
        ctrl2 = work_wires_reversed[i + 1]
        t = work_wires_reversed[i]
        gates.append(qml.Toffoli(wires=[ctrl1, ctrl2, t]))

    gates.append(qml.Toffoli(wires=[*control_wires[:2], work_wires[0]]))

    for i in reversed(range(len(work_wires) - 1)):
        ctrl1 = control_wires_reversed[i + 1]
        ctrl2 = work_wires_reversed[i + 1]
        t = work_wires_reversed[i]
        gates.append(qml.Toffoli(wires=[ctrl1, ctrl2, t]))

    return gates
    


class Controlled(Operator):
    r"""Wrapper denoting a controlled operation.

    Args:
        base (Operator): operation that is controlled
        control_wires (Any): the wires to control the operation on
        control_values (Bool, Iterable[Bool]): The values to control on, denoted by ``0``, ``1``,
            ``True``, or ``False``.  Must be same length as ``control_wires``
        work_wires (Any): optional work wires used to decompose the operation

    **Example:**

    The following is a CNOT gate:

    >>> op = Controlled(qml.PauliX(1), 0)
    >>> op.base
    PauliX(wires=[1])
    >>> op.get_matrix()
    array([[1.+0.j, 0.+0.j, 0.+0.j, 0.+0.j],
       [0.+0.j, 1.+0.j, 0.+0.j, 0.+0.j],
       [0.+0.j, 0.+0.j, 0.+0.j, 1.+0.j],
       [0.+0.j, 0.+0.j, 1.+0.j, 0.+0.j]])
    >>> op.control_wires
    <Wires = [0]>

    Integration doesn't work yet as device doesn't know what to do with it. We need to determine
    simulator support based on a ``has_matrix`` property.

    ... code-block:: python

        @qml.qnode(qml.device('default.qubit', wires=(0,1)))
        def circuit():
            qml.PauliX(0)
            Controlled(qml.PauliX(1), 0)
            return qml.state()

    """
    
    num_wires = AnyWires

    def __init__(self, base, control_wires, control_values=None, work_wires=None, do_queue=True, id=None):
        if isinstance(control_values, str):
            warnings.warn("Specifying control values as a string is deprecated. Please use Sequence[Bool]", UserWarning)
            control_values = [(x=="1") for x in control_values]

        self.base = base
        self._control_wires = Wires(control_wires)
        self._work_wires = Wires([]) if work_wires is None else Wires(work_wires)
        self._control_values = [1]*len(self._control_wires) if control_values is None else control_values
        self.hyperparameters['control_wires'] = self._control_wires
        self.hyperparameters['control_values'] = self._control_values
        self.hyperparameters['base']  = base
        self.hyperparameters['work_wires'] = self._work_wires
        super().__init__(*base.parameters, wires=(base.wires+self._control_wires+self._work_wires), do_queue=do_queue, id=id)
        self._name = f"C({self.base.name})"

    def queue(self, context=qml.QueuingContext):
        try:
             context.update_info(self.base, owner=self)
        except qml.queuing.QueuingError:
             self.base.queue(context=context)
             context.update_info(self.base, owner=self)

        context.append(self, owns=self.base)

        return self

    @property
    def control_wires(self):
        """The control wires."""
        return self._control_wires

    @property
    def work_wires(self):
        """Any work wires."""
        return self._work_wires

    @property
    def target_wires(self):
        """Wires of the base gate."""
        return self.base.wires

    @property
    def control_values(self):
        """The values to control on."""
        return self._control_values

    @property
    def data(self):
        """Base gate data."""
        return self.base.data
    
    @property
    def basis(self):
        return self.base.basis

    def label(self, decimals=None, base_label=None):
        return self.base.label(decimals=decimals, base_label=base_label)
    
    @staticmethod
    def compute_matrix(*args, base=None, control_wires=None, control_values=None, work_wires=None, **kwargs):
        base_matrix = base.compute_matrix(*args, **kwargs)
        
        base_matrix_size = qml.math.shape(base_matrix)[0]
        num_control_states = 2**len(control_wires)
        total_matrix_size = num_control_states * base_matrix_size

        if control_values is None:
            control_int = 0
        else:
            control_int = sum(2**i * v for i, v in enumerate(reversed(control_values)))

        padding_left = control_int * base_matrix_size
        padding_right = total_matrix_size - base_matrix_size - padding_left

        interface = qml.math.get_interface(base_matrix)
        left_pad = qml.math.cast_like(qml.math.eye(padding_left, like=interface), 1j)
        right_pad = qml.math.cast_like(qml.math.eye(padding_right, like=interface), 1j)
        
        return qml.math.block_diag([left_pad, base_matrix, right_pad])

    @staticmethod
    def compute_decomposition(*args, wires=None, base=None, control_wires=None, control_values=None,
        work_wires=None):

        flips = [qml.PauliX(w) for w, val in zip(control_wires, control_values) if not val]
        if len(control_wires) == 1:
            try:
                return flips+c1_decomp(base, control_wires)+flips
            except NoDecompositionShortcut:
                pass
        if len(control_wires) > 2 and isinstance(base, PauliX):
            return flips + multicx_decomposition(control_wires, base.wires, work_wires) + flips
        return qml.operation.DecompositionUndefinedError

    @staticmethod
    def compute_eigvals(*args, **kwargs):
        # what for this?
        raise qml.operation.EigvalsUndefinedError

    def generator(self):
        sub_gen = self.base.generator()
        proj_ones = np.ones(len(self.control_wires), requires_grad=False)
        proj = qml.Projector(proj_ones, wires=self.control_wires)
        return (1.0*proj @ sub_gen)

    def adjoint(self):
        return Controlled(self.base.adjoint(), self.control_wires, self.control_values, self.work_wires)

