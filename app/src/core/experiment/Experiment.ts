/**
 * Experiment constructor arguments.
 * NOTE: This is currently just the serialized experiment and thus
 * will have underscore-separated variable names
 */
type ExperimentArgs = SerializedExperiment;

interface MapobjectType {
    id: string;
    name: string;
    features: Feature[];
}

class Experiment implements Model {
    id: string;
    name: string;
    description: string;
    plateFormat: string;
    microscopeType: string;
    mapobjectTypes: MapobjectType[];
    plateAcquisitionMode: string;
    channels: Channel[] = [];
    workflowDescription: any;
    status: string;

    /**
     * Construct a new Experiment.
     * @class Experiment
     * @classdesc An experiment is the main container for data acquired by a 
     * microscope. Most of the functionality of TissueMAPS is provided by
     * the experiment object together with an object of type Viewer.
     * An experiment should be more of a data container and the viewer should
     * have the active role in the application.
     * @param {ExperimentArgs} args - Constructor arguments.
     */
    constructor(args: ExperimentArgs) {

        var $q = $injector.get<ng.IQService>('$q');

        this.id = args.id;
        this.name = args.name;
        this.description = args.description;
        this.status = args.status;
        this.plateFormat = args.plate_format;
        this.microscopeType = args.microscope_type;
        this.plateAcquisitionMode = args.plate_acquisition_mode;
        this.mapobjectTypes = args.mapobject_types;
        this.workflowDescription = args.workflow_description;

        args.channels.forEach((ch) => {
            var isFirstChannel = this.channels.length == 0;
            var channel = new Channel(_.extend(ch, {
                visible: isFirstChannel
            }));
            this.channels.push(channel);
        });
    }

    /**
     * The highest zoom level for any layer of this experiment.
     * It is assumed that all layers of an experiment have the same max
     * zoom level.
     * @type number
     */
    get maxZoom(): number {
        return this.channels[0].layers[0].maxZoom;
    }

    /**
     * The highest zplane supported by this experiment.
     * @type number
     */
    get maxZ(): number {
        var zs = this.channels.map((ch) => {
            return ch.maxZ;
        });
        return Math.max.apply(this, zs);
    }

    /**
     * The lowest zplane supported by this experiment.
     * @type number
     */
    get minZ(): number {
        var zs = this.channels.map((ch) => {
            return ch.minZ;
        });
        return Math.min.apply(this, zs);
    }

    // TODO: error handling
    static getAll(): ng.IPromise<Experiment[]> {
        var $http = $injector.get<ng.IHttpService>('$http');
        return $http.get('/api/experiments')
        .then((resp: { data: { experiments: SerializedExperiment[]; } }) => {
            var exps = resp.data.experiments;
            return exps.map((e) => {
                return new Experiment(e);
            });
        });
    }

    // TODO: error handling
    static get(id: string): ng.IPromise<Experiment> {
        var $http = $injector.get<ng.IHttpService>('$http');
        return $http.get('/api/experiments/' + id)
        .then((resp: {data: {experiment: SerializedExperiment}}) => {
            return new Experiment(resp.data.experiment);
        });
    }

    // TODO: error handling
    static delete(id: string): ng.IPromise<boolean> {
        var $http = $injector.get<ng.IHttpService>('$http');
        return $http.delete('/api/experiments/' + id)
        .then((resp) => {
            return true;
        })
        .catch((resp) => {
            return resp.data.error;
        });
    }

    static create(args: CreateExperimentArgs) {
        var $http = $injector.get<ng.IHttpService>('$http');
        var $q = $injector.get<ng.IQService>('$q');
        var deferredExp = $q.defer();
        $http.post('/api/experiments', {
            name: args.name,
            description: args.description,
            plate_format: args.plateFormat,
            microscope_type: args.microscopeType,
            plate_acquisition_mode: args.plateAcquisitionMode
        })
        .then((resp: {data: {experiment: SerializedExperiment}}) => {
            deferredExp.resolve(new Experiment(resp.data.experiment));
        })
        .catch((resp) => {
            deferredExp.reject(resp.data.error);
        });
        return deferredExp.promise;
    }

    submitWorkflow(workflowArgs) {
        var $http = $injector.get<ng.IHttpService>('$http');
        var $q = $injector.get<ng.IQService>('$q');
        return $http.post('/api/experiments/' + this.id + '/workflow', workflowArgs)
        .then((resp) => {
            console.log(resp);
            return resp.data;
        })
        .catch((resp) => {
            $q.reject(resp.data.error);
        });
    }
}
